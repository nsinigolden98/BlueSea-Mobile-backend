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


class PaymentsConsumer(AsyncWebsocketConsumer):
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
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.user_group = f"payments_user_{user.id}"
        self.reference_id = self.scope["url_route"]["kwargs"].get("reference_id")

        if self.reference_id:
            has_access = await self._check_reference_access(self.reference_id, user.id)
            if not has_access:
                await self.close(code=4403)
                return

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        if self.reference_id:
            await self.channel_layer.group_add(
                f"payment_{self.reference_id}", self.channel_name
            )

        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "user_id": user.id,
                    "reference_id": self.reference_id,
                    "message": "Subscribed to payment updates",
                }
            )
        )

    @database_sync_to_async
    def _check_reference_access(self, reference_id, user_id):
        try:
            from .models import (
                AirtimeTopUp,
                MTNDataTopUp,
                AirtelDataTopUp,
                GloDataTopUp,
                EtisalatDataTopUp,
                DSTVPayment,
                GOTVPayment,
                StartimesPayment,
                ShowMaxPayment,
                ElectricityPayment,
                WAECRegitration,
                WAECResultChecker,
                JAMBRegistration,
                Airtime2Cash,
                GroupPayment,
            )
            from django.db.models import Q

            for m in (
                AirtimeTopUp,
                MTNDataTopUp,
                AirtelDataTopUp,
                GloDataTopUp,
                EtisalatDataTopUp,
                DSTVPayment,
                GOTVPayment,
                StartimesPayment,
                ShowMaxPayment,
                ElectricityPayment,
                WAECRegitration,
                WAECResultChecker,
                JAMBRegistration,
                Airtime2Cash,
            ):
                if m.objects.filter(request_id=reference_id, user_id=user_id).exists():
                    return True
            if (
                GroupPayment.objects.filter(
                    Q(vtu_reference=reference_id)
                    | Q(service_details__request_id=reference_id)
                )
                .filter(Q(initiated_by_id=user_id) | Q(group__members__user_id=user_id))
                .exists()
            ):
                return True
            return False
        except Exception:
            return False

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "user_group"):
                await self.channel_layer.group_discard(
                    self.user_group, self.channel_name
                )
            if hasattr(self, "reference_id") and self.reference_id:
                await self.channel_layer.group_discard(
                    f"payment_{self.reference_id}", self.channel_name
                )
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except Exception:
            pass

    async def payment_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "payment_update",
                    "reference_id": event.get("reference_id"),
                    "status": event.get("status"),
                    "payment_type": event.get("payment_type"),
                    "vtpass_transaction_id": event.get("vtpass_transaction_id"),
                    "amount": str(event.get("amount") or ""),
                }
            )
        )
