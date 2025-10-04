from django.urls import path
from .views import (
    AirtimeTopUpViews, 
    JAMBRegistrationViews,
    WAECRegitrationViews,
    WAECResultCheckerViews,
    ElectricityPaymentViews,
    DSTVPaymentViews,
    GOTVPaymentViews,
    StartimesPaymentViews,
    ShowMaxPaymentViews,
    MTNDataTopUpViews,
    AirtelDataTopUpViews,
    GloDataTopUpViews,
    EtisalatDataTopUpViews,
    )

urlpatterns = [
    path('airtime/', AirtimeTopUpViews.as_view(), name='airtime'),
    path('airtel-data/', AirtelDataTopUpViews.as_view(),name='airtel-data'),
    path('mtn-data/', MTNDataTopUpViews.as_view(),  name='mtn-data'),
    path('glo-data/',GloDataTopUpViews.as_view(), name='glo-data'),
    path('etisalat-data/', EtisalatDataTopUpViews.as_view(), name='etisalat-data'),
    path('dstv/', DSTVPaymentViews.as_view(), name='dstv-payment'),
    path('gotv/', GOTVPaymentViews.as_view(), name='gotv-payment'),
    path('startimes/', StartimesPaymentViews.as_view(), name='startimes-payment'),
    path('showmax/', ShowMaxPaymentViews.as_view(), name='showmax-payment'),
    path('electricity/', ElectricityPaymentViews.as_view(), name='electricity-payment'),
    path('jamb-registration/', JAMBRegistrationViews.as_view(), name='jamb-registration'),
    path('waec-result/', WAECResultCheckerViews.as_view(), name='waec-result-checker'),
    path('waec-registration/', JAMBRegistrationViews.as_view(), name='waec-registration'),
    #path('airtime-buyback/', name='airtime-buyback'),
]
