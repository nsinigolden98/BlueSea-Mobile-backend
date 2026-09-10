from django.urls import path
from . import admin_view
from .views import SupportTicketListView, SupportTicketDetailView

urlpatterns = [
    path("", SupportTicketListView.as_view(), name="support-tickets"),
    path(
        "<int:ticket_id>/",
        SupportTicketDetailView.as_view(),
        name="support-ticket-detail",
    ),
    path("admin/", admin_view.admin_support, name="admin-support"),
    path(
        "admin/tickets/", admin_view.AdminTicketListView.as_view(), name="admin-tickets"
    ),
    path(
        "admin/tickets/<int:ticket_id>/",
        admin_view.AdminTicketDetailView.as_view(),
        name="admin-ticket-detail",
    ),
]
