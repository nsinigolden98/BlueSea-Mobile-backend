from django.urls import path

from .admin_view import AdminTicketDetailView, AdminTicketListView, AdminTicketReplyView
from .views import SupportTicketDetailView, SupportTicketListView

urlpatterns = [
    path("", SupportTicketListView.as_view(), name="support-tickets"),
    path(
        "<int:ticket_id>/",
        SupportTicketDetailView.as_view(),
        name="support-ticket-detail",
    ),
    path("admin/tickets/", AdminTicketListView.as_view(), name="admin-tickets"),
    path(
        "admin/tickets/<int:ticket_id>/",
        AdminTicketDetailView.as_view(),
        name="admin-ticket-detail",
    ),
    path(
        "admin/tickets/<int:ticket_id>/reply/",
        AdminTicketReplyView.as_view(),
        name="admin-ticket-reply",
    ),
]
