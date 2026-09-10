import json
import logging
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_str):
    try:
        UntypedToken(token_str)
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.settings import api_settings

        validated = UntypedToken(token_str)
        user_id = validated.get(api_settings.USER_ID_CLAIM)
        if user_id:
            return User.objects.filter(id=user_id).first()
    except (InvalidToken, TokenError, Exception) as e:
        logger.debug(f"WS auth failed: {e}")
    return None


class SupportConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0] or params.get("access", [None])[0]

        if not token:
            auth_header = (
                dict(self.scope.get("headers", {})).get(b"authorization", b"").decode()
            )
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:]

        user = await get_user_from_token(token) if token else None
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close(code=4401)
            return

        self.user = user
        self.ticket_id = self.scope["url_route"]["kwargs"].get("ticket_id")

        await self.channel_layer.group_add(f"support_user_{user.id}", self.channel_name)

        if self.ticket_id:
            await self.channel_layer.group_add(
                f"support_ticket_{self.ticket_id}", self.channel_name
            )

        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "user_id": user.id,
                    "user_name": f"{user.surname} {user.other_names}",
                    "ticket_id": self.ticket_id,
                }
            )
        )

    async def disconnect(self, code):
        try:
            await self.channel_layer.group_discard(
                f"support_user_{self.user.id}", self.channel_name
            )
            if hasattr(self, "ticket_id") and self.ticket_id:
                await self.channel_layer.group_discard(
                    f"support_ticket_{self.ticket_id}", self.channel_name
                )
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
            event_type = data.get("type")

            if event_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            elif event_type == "send_message":
                result = await self._handle_send_message(data)
                if result:
                    await self.channel_layer.group_send(
                        f"support_ticket_{data.get('ticket_id')}", result
                    )
            elif event_type == "update_status":
                result = await self._handle_update_status(data)
                if result:
                    await self.channel_layer.group_send(
                        f"support_ticket_{data.get('ticket_id')}", result
                    )
            elif event_type == "update_priority":
                result = await self._handle_update_priority(data)
                if result:
                    await self.channel_layer.group_send(
                        f"support_ticket_{data.get('ticket_id')}", result
                    )
        except Exception as e:
            logger.error(f"SupportConsumer receive error: {e}")

    @database_sync_to_async
    def _handle_send_message(self, data):
        from support.models import SupportTicket, SupportMessage, SupportAttachment

        ticket_id = data.get("ticket_id")
        message_text = data.get("message", "")
        is_admin = data.get("is_admin", True)
        images = data.get("images", [])

        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            message = SupportMessage.objects.create(
                ticket=ticket,
                sender=self.user,
                message=message_text,
                is_admin=is_admin,
            )

            for image_url in images:
                try:
                    import uuid
                    from django.core.files.base import ContentFile
                    import base64

                    format, imgstr = image_url.split(";base64,")
                    ext = format.split("/")[-1]
                    data_bytes = base64.b64decode(imgstr)
                    file_name = f"support_attachment_{uuid.uuid4().hex[:8]}.{ext}"
                    image_file = ContentFile(data_bytes, name=file_name)

                    SupportAttachment.objects.create(
                        message=message,
                        image=image_file,
                    )
                except Exception:
                    pass

            return {
                "type": "new_message",
                "ticket_id": ticket_id,
                "message": {
                    "id": message.id,
                    "sender_name": f"{self.user.surname} {self.user.other_names}",
                    "message": message_text,
                    "is_admin": is_admin,
                    "created_at": message.created_at.isoformat(),
                },
            }

        except SupportTicket.DoesNotExist:
            return None

    @database_sync_to_async
    def _handle_update_status(self, data):
        from support.models import SupportTicket

        ticket_id = data.get("ticket_id")
        new_status = data.get("status")
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            ticket.status = new_status
            ticket.save(update_fields=["status"])
            return {
                "type": "status_update",
                "ticket_id": ticket_id,
                "status": new_status,
            }
        except SupportTicket.DoesNotExist:
            return None

    @database_sync_to_async
    def _handle_update_priority(self, data):
        from support.models import SupportTicket

        ticket_id = data.get("ticket_id")
        new_priority = data.get("priority")
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            ticket.priority = new_priority
            ticket.save(update_fields=["priority"])
            return {
                "type": "priority_update",
                "ticket_id": ticket_id,
                "priority": new_priority,
            }
        except SupportTicket.DoesNotExist:
            return None

    async def message_event(self, event):
        await self.send(text_data=json.dumps(event["event_data"]))

    async def status_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def priority_update(self, event):
        await self.send(text_data=json.dumps(event))
