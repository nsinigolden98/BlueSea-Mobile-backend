from django.urls import path
from .views import (
    AutoTopUpCreateView,
    GetUserAutoTopUpsView,
    AutoTopUpDetailView,
    AutoTopUpCancelView,
    AutoTopUpReactivateView,
    AutoTopUpHistoryView
)

urlpatterns = [
    path('create/', AutoTopUpCreateView.as_view(), name='auto-topup-create'),
    path('list/', GetUserAutoTopUpsView.as_view(), name='auto-topup-list'),
    path('<int:pk>/', AutoTopUpDetailView.as_view(), name='auto-topup-detail'),
    path('<int:pk>/cancel/', AutoTopUpCancelView.as_view(), name='auto-topup-cancel'),
    path('<int:pk>/reactivate/', AutoTopUpReactivateView.as_view(), name='auto-topup-reactivate'),
    path('<int:pk>/history/', AutoTopUpHistoryView.as_view(), name='auto-topup-history'),
]