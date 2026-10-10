import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

logger = logging.getLogger(__name__)
User = get_user_model()


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
def _get_unread_count(user_id):
    from notifications.models import Notification

    return Notification.objects.filter(user_id=user_id, is_read=False).count()


@database_sync_to_async
def _mark_one_read(user_id, notification_id):
    from notifications.models import Notification

    try:
        notification = Notification.objects.get(id=notification_id, user_id=user_id)
    except (Notification.DoesNotExist, ValueError, TypeError):
        return None, 0, False
    notification.mark_as_read()
    unread = Notification.objects.filter(user_id=user_id, is_read=False).count()
    return (
        {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat()
            if notification.created_at
            else None,
            "read_at": notification.read_at.isoformat()
            if notification.read_at
            else None,
        },
        unread,
        True,
    )


@database_sync_to_async
def _mark_all_read(user_id):
    from django.utils import timezone

    from notifications.models import Notification

    updated = Notification.objects.filter(user_id=user_id, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    return updated, 0


class NotificationConsumer(AsyncWebsocketConsumer):
    """Real-time user notifications.

    Auth: ?token=<JWT> or Authorization: Bearer <JWT>.
    Each connection joins notifications_user_{id} so all devices stay in sync.
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
        self.notify_group = f"notifications_user_{user.id}"

        await self.channel_layer.group_add(self.notify_group, self.channel_name)
        await self.accept()
        unread = await _get_unread_count(user.id)
        await self.send(
            text_data=json.dumps(
                {"type": "connected", "user_id": user.id, "unread_count": unread}
            )
        )

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "notify_group"):
                await self.channel_layer.group_discard(
                    self.notify_group, self.channel_name
                )
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

        msg_type = data.get("type")
        if msg_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return
        if msg_type == "unread_count_request":
            unread = await _get_unread_count(self.user_id)
            await self.send(
                text_data=json.dumps({"type": "unread_count", "unread_count": unread})
            )
            return
        if msg_type == "mark_read":
            await self._on_mark_read(data)
            return
        if msg_type == "mark_all_read":
            updated, unread = await _mark_all_read(self.user_id)
            await self.channel_layer.group_send(
                self.notify_group,
                {
                    "type": "read_event",
                    "event_data": {
                        "type": "read_receipt",
                        "action": "mark_all_read",
                        "updated_count": updated,
                        "unread_count": unread,
                    },
                },
            )
            return
        await self._send_error(f"Unknown type '{msg_type}'.")

    async def _on_mark_read(self, data):
        notification_id = data.get("notification_id")
        if notification_id is None:
            await self._send_error("notification_id is required.")
            return
        try:
            notification_id = int(notification_id)
        except (TypeError, ValueError):
            await self._send_error("Invalid notification_id.")
            return
        payload, unread, found = await _mark_one_read(self.user_id, notification_id)
        if not found:
            await self._send_error("Notification not found.")
            return
        await self.channel_layer.group_send(
            self.notify_group,
            {
                "type": "read_event",
                "event_data": {
                    "type": "read_receipt",
                    "notification_id": notification_id,
                    "notification": payload,
                    "is_read": True,
                    "unread_count": unread,
                },
            },
        )

    async def _send_error(self, detail):
        try:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": detail})
            )
        except Exception:
            logger.debug("WS error send failed: %s", detail)

    async def notification_event(self, event):
        await self.send(text_data=json.dumps(event["event_data"]))

    async def read_event(self, event):
        await self.send(text_data=json.dumps(event["event_data"]))
