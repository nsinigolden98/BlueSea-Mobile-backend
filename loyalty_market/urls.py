from django.urls import path
from loyalty_market.views import (
    RewardListView, RewardDetailView, UserPointsView,
    AdminCreateRewardView, RedeemPointsView,
    CreateEventView, EventListView, EventDetailView,
    PurchaseTicketView, MyTicketsView, ScanTicketView,
    ExportAttendeesView
)

urlpatterns = [
    # Reward endpoints
    path('rewards/', RewardListView.as_view(), name='reward-list'),
    path('rewards/<uuid:reward_id>/', RewardDetailView.as_view(), name='reward-detail'),
    path('user/points/', UserPointsView.as_view(), name='user-points'),
    path('rewards/create/', AdminCreateRewardView.as_view(), name='admin-create-reward'),
    path('rewards/redeem/', RedeemPointsView.as_view(), name='redeem-points'),
    
    # Ticketing endpoints
    path('events/create/', CreateEventView.as_view(), name='create-event'),
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/<uuid:event_id>/', EventDetailView.as_view(), name='event-detail'),
    path('tickets/purchase/', PurchaseTicketView.as_view(), name='purchase-ticket'),
    path('tickets/my/', MyTicketsView.as_view(), name='my-tickets'),
    path('tickets/scan/', ScanTicketView.as_view(), name='scan-ticket'),
    path('events/<uuid:event_id>/attendees/export/', ExportAttendeesView.as_view(), name='export-attendees'),
]