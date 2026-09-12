"""
ASGI config for bluesea_mobile project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bluesea_mobile.settings")

from django.core.asgi import get_asgi_application

django_asgi = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

import payments.routing
import support.routing
import wallet.routing

ws_patterns = (
    payments.routing.websocket_urlpatterns
    + support.routing.websocket_urlpatterns
    + wallet.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi,
        "websocket": AuthMiddlewareStack(URLRouter(ws_patterns)),
    }
)
