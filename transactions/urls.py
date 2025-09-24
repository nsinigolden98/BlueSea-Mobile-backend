from django.urls import path
from .views import *

urlpatterns = [
    path('history/', GetWalletTransaction.as_view(), name='wallet-transactions'),
    path('fund-wallet/', InitializeFunding.as_view(), name='initialize-funding'),
    path('webhook/paystack/', PaymentWebhook.as_view(), name='paystack-webhook'),
]