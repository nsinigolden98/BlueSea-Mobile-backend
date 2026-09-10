"""
ASGI config for bluesea_mobile project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bluesea_mobile.settings")

django_asgi = get_asgi_application()

try:
    import payments.routing
    import support.routing

    ws_patterns = payments.routing.websocket_urlpatterns + support.routing.websocket_urlpatterns
except Exception:
    ws_patterns = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi,
        "websocket": AuthMiddlewareStack(URLRouter(ws_patterns)),
    }
)
