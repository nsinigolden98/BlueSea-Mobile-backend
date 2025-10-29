from django.urls import path
from . import views

app_name = 'bonus'

urlpatterns = [
    path('summary/', views.BonusPointsSummaryView.as_view(), name='summary'),
    path('history/', views.BonusHistoryView.as_view(), name='history'),
   # path('redeem/', views.RedeemPointsView.as_view(), name='redeem'),
    path('daily-login/', views.ClaimDailyLoginView.as_view(), name='daily-login'),
    path('campaigns/', views.ActiveCampaignsView.as_view(), name='campaigns'),
]