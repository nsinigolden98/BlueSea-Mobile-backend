from django.urls import path
from .views import (
    RewardListView,
    RewardDetailView,
    RedeemRewardView,
    UserRedemptionsView,
)

urlpatterns = [
    path("rewards/", RewardListView.as_view(), name="reward-list"),
    path("rewards/<uuid:reward_id>/", RewardDetailView.as_view(), name="reward-detail"),
    path(
        "rewards/<uuid:reward_id>/redeem/",
        RedeemRewardView.as_view(),
        name="redeem-reward",
    ),
    path("redemptions/", UserRedemptionsView.as_view(), name="user-redemptions"),
]
