from django.urls import path

from .views import (
    AffiliateAttributionView,
    AffiliateDashboardView,
    AffiliateLinkView,
    AffiliatePayoutView,
    AffiliateSalesListView,
    AffiliateStatusView,
    ApplyAffiliateView,
)

urlpatterns = [
    path("apply/", ApplyAffiliateView.as_view(), name="affiliate-apply"),
    path("status/", AffiliateStatusView.as_view(), name="affiliate-status"),
    path("links/", AffiliateLinkView.as_view(), name="affiliate-links"),
    path(
        "attribution/", AffiliateAttributionView.as_view(), name="affiliate-attribution"
    ),
    path("dashboard/", AffiliateDashboardView.as_view(), name="affiliate-dashboard"),
    path("sales/", AffiliateSalesListView.as_view(), name="affiliate-sales"),
    path("payout/", AffiliatePayoutView.as_view(), name="affiliate-payout"),
]
