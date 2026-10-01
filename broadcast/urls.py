from django.urls import path

from .views import BroadcastHistoryView, ImportantBroadcastView, NewMonthBroadcastView

urlpatterns = [
    path("new-month/", NewMonthBroadcastView.as_view(), name="broadcast-new-month"),
    path("important/", ImportantBroadcastView.as_view(), name="broadcast-important"),
    path("", BroadcastHistoryView.as_view(), name="broadcast-history"),
]
