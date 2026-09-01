from django.urls import re_path
from .consumers import PaymentsConsumer

websocket_urlpatterns = [
    re_path(r"ws/payments/$", PaymentsConsumer.as_view()),
    re_path(r"ws/payments/(?P<reference_id>[^/]+)/$", PaymentsConsumer.as_view()),
]
