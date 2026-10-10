from django.urls import path
from .views import *
from .nomba_views import (
    NombaAccountNameView,
    NombaDvaAssignView,
    NombaDvaConfirmView,
    NombaInitializeFunding,
    NombaPaymentWebhook,
)

urlpatterns = [
    path("history/", GetWalletTransaction.as_view(), name="wallet-transactions"),
    path("fund-wallet/", InitializeFunding.as_view(), name="initialize-funding"),
    path("webhook/paystack/", PaymentWebhook.as_view(), name="paystack-webhook"),
    path("account-name/", AccountNameView.as_view(), name="account-name"),
    path("dva/refresh/", DvaRefreshView.as_view(), name="dva-refresh"),
    path("nomba/fund-wallet/", NombaInitializeFunding.as_view(), name="nomba-initialize-funding"),
    path("nomba/account-name/", NombaAccountNameView.as_view(), name="nomba-account-name"),
    path("nomba/dva/assign/", NombaDvaAssignView.as_view(), name="nomba-dva-assign"),
    path("nomba/dva/confirm/", NombaDvaConfirmView.as_view(), name="nomba-dva-confirm"),
    path("nomba/webhook/", NombaPaymentWebhook.as_view(), name="nomba-webhook"),
]
