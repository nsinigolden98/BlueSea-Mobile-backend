from django.urls import path
from .views import (
    CreateEventView, EventListView, EventDetailView,
    PurchaseTicketView, MyTicketsView, ScanTicketView,
    ExportAttendeesView, CreateTicketVendor, VendorStatusView
)
from .admin_views import reject_vendors_with_reason
from .views import TicketListView, TicketDetailView, MyTicketsListView, TransferTicketView, CancelTicketView, ScannerDashboardView, MyScannerAssignmentsView, AddEventScannerView

urlpatterns = [
    path('vendor/create/', CreateTicketVendor.as_view(), name='create-vendor'),
    path('vendor/status/', VendorStatusView.as_view(), name='vendor-status'),
    path('events/create/', CreateEventView.as_view(), name='create-event'),
    path('events/all/', EventListView.as_view(), name='event-list'),
    path('events/<uuid:event_id>/', EventDetailView.as_view(), name='event-detail'),

    #purchase ticket
    path('events/<uuid:event_id>/purchase/', PurchaseTicketView.as_view(), name='purchase-ticket'),
    path('tickets/my/', MyTicketsView.as_view(), name='my-tickets'),
    path('tickets/scan/', ScanTicketView.as_view(), name='scan-ticket'),
    path('events/<uuid:event_id>/attendees/export/', ExportAttendeesView.as_view(), name='export-attendees'),
    # Ticket management endpoints
    path('tickets/', TicketListView.as_view(), name='ticket-list'),
    path('tickets/<uuid:ticket_id>/', TicketDetailView.as_view(), name='ticket-detail'),
    path('mytickets/', MyTicketsListView.as_view(), name='my-tickets'),
    path('tickets/<uuid:ticket_id>/transfer/', TransferTicketView.as_view(), name='transfer-ticket'),
    path('tickets/<uuid:ticket_id>/cancel/', CancelTicketView.as_view(), name='cancel-ticket'),
    # Scanner endpoints
    path('tickets/scan/', ScanTicketView.as_view(), name='scan-ticket'),
    path('events/<uuid:event_id>/scan-stats/', ScannerDashboardView.as_view(), name='scanner-dashboard'),
    path('my-scanner-assignments/', MyScannerAssignmentsView.as_view(), name='my-scanner-assignments'),
    path('events/<uuid:event_id>/scanner/', AddEventScannerView.as_view(), name='add-event-scanner'),
]