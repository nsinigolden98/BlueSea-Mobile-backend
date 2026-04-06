from django.urls import path
from .views import SupportTicketListView, SupportTicketDetailView

urlpatterns = [
    path("", SupportTicketListView.as_view(), name="support-tickets"),
    path(
        "<int:ticket_id>/",
        SupportTicketDetailView.as_view(),
        name="support-ticket-detail",
    ),
]
