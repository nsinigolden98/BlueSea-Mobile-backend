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


class WalletBalanceConsumer(AsyncWebsocketConsumer):
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
        self.wallet_group = f"wallet_user_{user.id}"

        await self.channel_layer.group_add(self.wallet_group, self.channel_name)
        await self.accept()

        balances = await self._get_balances(user.id)
        await self.send(
            text_data=json.dumps({"type": "connected", "user_id": user.id, **balances})
        )

    @database_sync_to_async
    def _get_balances(self, user_id):
        from wallet.models import Wallet

        try:
            wallet = Wallet.objects.get(user_id=user_id)
            return {
                "balance": str(wallet.balance),
                "balance_formatted": f"₦{wallet.balance:,.2f}",
                "locked_balance": str(wallet.locked_balance),
                "locked_balance_formatted": f"₦{wallet.locked_balance:,.2f}",
                "available_balance": str(wallet.available_balance),
                "available_balance_formatted": f"₦{wallet.available_balance:,.2f}",
            }
        except Wallet.DoesNotExist:
            return {
                "balance": "0.00",
                "balance_formatted": "₦0.00",
                "locked_balance": "0.00",
                "locked_balance_formatted": "₦0.00",
                "available_balance": "0.00",
                "available_balance_formatted": "₦0.00",
            }

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "wallet_group"):
                await self.channel_layer.group_discard(
                    self.wallet_group, self.channel_name
                )
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
            msg_type = data.get("type")
            if msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            elif msg_type == "balance_request":
                balances = await self._get_balances(self.user.id)
                await self.send(
                    text_data=json.dumps({"type": "balance_update", **balances})
                )
        except Exception:
            pass

    async def wallet_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "balance_update",
                    "balance": event.get("balance"),
                    "balance_formatted": event.get("balance_formatted"),
                    "locked_balance": event.get("locked_balance"),
                    "locked_balance_formatted": event.get("locked_balance_formatted"),
                    "available_balance": event.get("available_balance"),
                    "available_balance_formatted": event.get(
                        "available_balance_formatted"
                    ),
                    "amount": event.get("amount"),
                    "reference": event.get("reference"),
                    "description": event.get("description"),
                    "transaction_type": event.get("transaction_type"),
                }
            )
        )
