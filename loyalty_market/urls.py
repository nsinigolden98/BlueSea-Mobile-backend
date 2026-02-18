# from django.urls import path
# from loyalty_market.views import (
#     RewardListView, RewardDetailView, UserPointsView,
#     AdminCreateRewardView, RedeemPointsView,
#     CreateEventView, EventListView, EventDetailView,
#     PurchaseTicketView, MyTicketsView, ScanTicketView,
#     ExportAttendeesView
# )

# urlpatterns = [
#     # Reward endpoints
#     path('rewards/', RewardListView.as_view(), name='reward-list'),
#     path('rewards/<uuid:reward_id>/', RewardDetailView.as_view(), name='reward-detail'),
#     path('user/points/', UserPointsView.as_view(), name='user-points'),
#     path('rewards/create/', AdminCreateRewardView.as_view(), name='admin-create-reward'),
#     path('rewards/redeem/', RedeemPointsView.as_view(), name='redeem-points'),
    
#     # Ticketing endpoints
    
# ]