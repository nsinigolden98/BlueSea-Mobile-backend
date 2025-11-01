from django.urls import path
from loyalty_market.views import RewardListView, RewardDetailView, UserPointsView

urlpatterns = [
    path('rewards/', RewardListView.as_view(), name='reward-list'),
    path('rewards/<uuid:reward_id>/', RewardDetailView.as_view(), name='reward-detail'),
    path('user/points/', UserPointsView.as_view(), name='user-points'),
]