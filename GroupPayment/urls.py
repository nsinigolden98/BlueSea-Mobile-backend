from django.urls import path,include
from . import views

app_name = 'group_payment'


urlpatterns = [
    path('create_group_payment/',views.CreateGroupPayme , name='create_group_payment'),
    path('join_group_payment/', , name='join_group_payment'),
]