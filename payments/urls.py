from django.urls import path
from .views import AirtimeTopUpViews

urlpatterns = [
    path('airtime_top_up/', AirtimeTopUpViews.as_view(), name='top_up'),
    #path('data_top_up/', top_up, name='top_up'),
]
