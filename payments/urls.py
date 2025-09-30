from django.urls import path
from .views import (
    AirtimeTopUpViews, 
    JAMBRegistrationViews,
    WAECRegitrationViews,
    WAECResultCheckerViews,
    ElectricityPaymentViews,
    )

urlpatterns = [
    path('airtime/', AirtimeTopUpViews.as_view(), name='educational-payment'),
    #path('data_top_up/', top_up, name='top_up'),
    path('electricity/', ElectricityPaymentViews.as_view(), name='electricity-payment'),
    path('jamb-registration/', JAMBRegistrationViews.as_view(), name='jamb-registration'),
    path('waec-result/', WAECResultCheckerViews.as_view(), name='waec-result-checker'),
    path('waec-registration/', JAMBRegistrationViews.as_view(), name='waec-registration'),
]
