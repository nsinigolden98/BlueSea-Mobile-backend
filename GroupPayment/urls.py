from django.urls import path,include
from . import views

app_name = 'GroupPayment'


urlpatterns = [
    path('create_group_payment/', , name=''),
    path('/', , name=''),
]