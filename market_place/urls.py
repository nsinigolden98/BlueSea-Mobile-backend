from django.urls import path
from .views import (
    CreateEventView, EventListView, EventDetailView,
    PurchaseTicketView, MyTicketsView, ScanTicketView,
    ExportAttendeesView, CreateTicketVendor, VendorStatusView
)
from .admin_views import reject_vendors_with_reason

urlpatterns = [
    path('vendor/create/', CreateTicketVendor.as_view(), name='create-vendor'),
    path('vendor/status/', VendorStatusView.as_view(), name='vendor-status'),
    path('events/create/', CreateEventView.as_view(), name='create-event'),
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/<uuid:event_id>/', EventDetailView.as_view(), name='event-detail'),
    path('tickets/purchase/', PurchaseTicketView.as_view(), name='purchase-ticket'),
    path('tickets/my/', MyTicketsView.as_view(), name='my-tickets'),
    path('tickets/scan/', ScanTicketView.as_view(), name='scan-ticket'),
    path('events/<uuid:event_id>/attendees/export/', ExportAttendeesView.as_view(), name='export-attendees'),
    ]