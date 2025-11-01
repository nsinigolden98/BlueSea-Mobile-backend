from django.urls import path
from . import views

urlpatterns = [
    path('balance/', views.WalletBalance.as_view(), name='wallet-balance'),
]