import base64
import binascii
import json
import logging
import uuid
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

logger = logging.getLogger(__name__)
User = get_user_model()

ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_MESSAGE = 3


@database_sync_to_async
def get_user_from_token(token_str):
    try:
        UntypedToken(token_str)
        from rest_framework_simplejwt.settings import api_settings

        validated = UntypedToken(token_str)
        user_id = validated.get(api_settings.USER_ID_CLAIM)
        if user_id:
            return User.objects.filter(id=user_id).first()
    except (InvalidToken, TokenError, Exception) as e:
        logger.debug(f"WS auth failed: {e}")
    return None


@database_sync_to_async
def _get_ticket_access(ticket_id):
    """Return (exists, owner_profile_id) for a ticket. None owner on missing."""
    from support.models import SupportTicket

    try:
        ticket = SupportTicket.objects.only("id", "user_id").get(id=ticket_id)
        return True, ticket.user_id
    except (SupportTicket.DoesNotExist, ValueError, TypeError):
        return False, None


def _decode_data_url_image(data_url):
    """Validate a data-URL image and return (ContentFile, ext). Raises ValueError."""
    if not isinstance(data_url, str) or ";base64," not in data_url:
        raise ValueError("Image must be a data URL (data:image/<type>;base64,...).")
    try:
        header, imgstr = data_url.split(";base64,", 1)
    except ValueError:
        raise ValueError("Malformed image data URL.")
    if not header.startswith("data:image/"):
        raise ValueError("Only image data URLs are allowed.")
    ext = header.split("/")[-1].lower().split(";")[0].strip()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError(f"Unsupported image type '{ext}'.")
    try:
        raw = base64.b64decode(imgstr, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Invalid base64 image data.")
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image must be non-empty and <= {MAX_IMAGE_BYTES // (1024 * 1024)}MB."
        )
    ext = "jpg" if ext == "jpeg" else ext
    file_name = f"support_attachment_{uuid.uuid4().hex[:8]}.{ext}"
    return ContentFile(raw, name=file_name), ext


@database_sync_to_async
def _create_chat_message(ticket_id, sender_id, text, image_data_urls, is_admin):
    from support.models import SupportAttachment, SupportMessage, SupportTicket

    try:
        ticket = SupportTicket.objects.select_related("user").get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return {"ok": False, "error": "Ticket not found."}
    if not is_admin and ticket.user_id != sender_id:
        return {"ok": False, "error": "Not allowed on this ticket."}

    text = (text or "").strip()
    image_data_urls = image_data_urls or []
    if not text and not image_data_urls:
        return {"ok": False, "error": "Message text or images required."}
    if len(image_data_urls) > MAX_IMAGES_PER_MESSAGE:
        return {
            "ok": False,
            "error": f"Max {MAX_IMAGES_PER_MESSAGE} images per message.",
        }

    files = []
    for data_url in image_data_urls:
        try:
            files.append(_decode_data_url_image(data_url))
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    sender = User.objects.filter(id=sender_id).first()
    if sender is None:
        return {"ok": False, "error": "Sender not found."}

    message = SupportMessage.objects.create(
        ticket=ticket,
        sender=sender,
        message=text,
        is_admin=is_admin,
    )
    attachments = []
    for image_file, _ext in files:
        att = SupportAttachment.objects.create(message=message, image=image_file)
        url = att.image.url if att.image else None
        attachments.append({"id": att.id, "image": url})
    # refresh updated_at via save (auto_now)
    ticket.save(update_fields=["updated_at"])

    return {
        "ok": True,
        "owner_id": ticket.user_id,
        "payload": {
            "type": "new_message",
            "ticket_id": ticket.id,
            "message": {
                "id": message.id,
                "sender_id": sender.id,
                "sender_name": f"{sender.surname} {sender.other_names}".strip(),
                "message": message.message,
                "is_admin": message.is_admin,
                "attachments": attachments,
                "created_at": message.created_at.isoformat(),
            },
        },
    }


@database_sync_to_async
def _update_ticket_field(ticket_id, sender_id, is_admin, field, value):
    from support.models import SupportTicket

    if not is_admin:
        return {"ok": False, "error": "Admin only."}
    if field == "status":
        valid = dict(SupportTicket.STATUS_CHOICES)
        event_type = "status_update"
    else:
        valid = dict(SupportTicket.PRIORITY_CHOICES)
        event_type = "priority_update"
    if value not in valid:
        return {"ok": False, "error": f"Invalid {field} '{value}'."}
    try:
        ticket = SupportTicket.objects.select_related("user").get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return {"ok": False, "error": "Ticket not found."}
    setattr(ticket, field, value)
    ticket.save(update_fields=[field, "updated_at"])
    return {
        "ok": True,
        "owner_id": ticket.user_id,
        "payload": {"type": event_type, "ticket_id": ticket.id, field: value},
    }


class SupportConsumer(AsyncWebsocketConsumer):
    """Customer + admin live chat over a ticket room.

    History comes from REST (GET /support/<id>/); WS carries live events only.
    Auth: ?token=<JWT> or Authorization: Bearer <JWT>. Admin = user.is_admin.
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0] or params.get("access", [None])[0]

        if not token:
            auth_header = (
                dict(self.scope.get("headers", {})).get(b"authorization", b"").decode()
            )
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()

        user = await get_user_from_token(token) if token else None
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.user_id = user.id
        self.is_admin = bool(getattr(user, "is_admin", False))
        self.ticket_id = self.scope.get("url_route", {}).get("kwargs", {}).get(
            "ticket_id"
        )
        # normalize ticket_id to int when present
        if self.ticket_id is not None:
            try:
                self.ticket_id = int(self.ticket_id)
            except (TypeError, ValueError):
                await self.close(code=4404)
                return
        self._groups = []

        await self.channel_layer.group_add(
            f"support_user_{self.user_id}", self.channel_name
        )
        self._groups.append(f"support_user_{self.user_id}")

        owner_id = None
        if self.ticket_id is not None:
            exists, owner_id = await _get_ticket_access(self.ticket_id)
            if not exists:
                await self.close(code=4404)
                return
            if not self.is_admin and owner_id != self.user_id:
                await self.close(code=4403)
                return
            ticket_group = f"support_ticket_{self.ticket_id}"
            await self.channel_layer.group_add(ticket_group, self.channel_name)
            self._groups.append(ticket_group)
            # Admins also listen on the owner's user group so they get echoes
            # when the customer uses the base route; customers already have it.
            if self.is_admin and owner_id is not None:
                owner_group = f"support_user_{owner_id}"
                if owner_group not in self._groups:
                    await self.channel_layer.group_add(
                        owner_group, self.channel_name
                    )
                    self._groups.append(owner_group)

        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "user_id": self.user_id,
                    "user_name": f"{user.surname} {user.other_names}".strip(),
                    "is_admin": self.is_admin,
                    "ticket_id": self.ticket_id,
                }
            )
        )

    async def disconnect(self, code):
        for group in getattr(self, "_groups", []):
            try:
                await self.channel_layer.group_discard(group, self.channel_name)
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except (json.JSONDecodeError, TypeError):
            await self._send_error("Invalid JSON.")
            return
        if not isinstance(data, dict):
            await self._send_error("Invalid payload.")
            return

        event_type = data.get("type")
        if event_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return
        if event_type == "send_message":
            await self._on_send_message(data)
            return
        if event_type == "update_status":
            await self._on_update_field(data, "status")
            return
        if event_type == "update_priority":
            await self._on_update_field(data, "priority")
            return
        await self._send_error(f"Unknown type '{event_type}'.")

    async def _resolve_ticket_id(self, data):
        ticket_id = data.get("ticket_id", self.ticket_id)
        if ticket_id is None:
            return None
        try:
            return int(ticket_id)
        except (TypeError, ValueError):
            return "invalid"

    async def _on_send_message(self, data):
        ticket_id = await self._resolve_ticket_id(data)
        if ticket_id is None:
            await self._send_error("ticket_id is required.")
            return
        if ticket_id == "invalid":
            await self._send_error("Invalid ticket_id.")
            return
        if self.ticket_id is not None and ticket_id != self.ticket_id:
            await self._send_error("ticket_id does not match this connection.")
            return
        images = data.get("images", [])
        if images is None:
            images = []
        if not isinstance(images, list):
            await self._send_error("images must be an array of data URLs.")
            return

        result = await _create_chat_message(
            ticket_id,
            self.user_id,
            data.get("message", ""),
            images,
            self.is_admin,
        )
        if not result.get("ok"):
            await self._send_error(result.get("error", "Could not send message."))
            return
        payload = result["payload"]
        ticket_group = f"support_ticket_{ticket_id}"
        await self.channel_layer.group_send(
            ticket_group, {"type": "message_event", "event_data": payload}
        )
        owner_group = f"support_user_{result.get('owner_id')}"
        if owner_group not in (getattr(self, "_groups", []) + [ticket_group]):
            await self.channel_layer.group_send(
                owner_group, {"type": "message_event", "event_data": payload}
            )

    async def _on_update_field(self, data, field):
        if not self.is_admin:
            await self._send_error("Admin only.")
            return
        ticket_id = await self._resolve_ticket_id(data)
        if ticket_id is None:
            await self._send_error("ticket_id is required.")
            return
        if ticket_id == "invalid":
            await self._send_error("Invalid ticket_id.")
            return
        if self.ticket_id is not None and ticket_id != self.ticket_id:
            await self._send_error("ticket_id does not match this connection.")
            return
        result = await _update_ticket_field(
            ticket_id, self.user_id, self.is_admin, field, data.get(field)
        )
        if not result.get("ok"):
            await self._send_error(result.get("error", "Could not update ticket."))
            return
        payload = result["payload"]
        channel_type = "status_event" if field == "status" else "priority_event"
        await self.channel_layer.group_send(
            f"support_ticket_{ticket_id}",
            {"type": channel_type, "event_data": payload},
        )

    async def _send_error(self, detail):
        try:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": detail})
            )
        except Exception:
            logger.debug("WS error send failed: %s", detail)

    async def message_event(self, event):
        await self.send(text_data=json.dumps(event["event_data"]))

    async def status_event(self, event):
        await self.send(text_data=json.dumps(event["event_data"]))

    async def priority_event(self, event):
        await self.send(text_data=json.dumps(event["event_data"]))
