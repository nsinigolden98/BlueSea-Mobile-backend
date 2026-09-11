from django.urls import re_path

from .consumers import WalletBalanceConsumer

websocket_urlpatterns = [
    re_path(r"ws/wallet/?$", WalletBalanceConsumer.as_asgi()),
    re_path(r"ws/wallet/balance/?$", WalletBalanceConsumer.as_asgi()),
]
