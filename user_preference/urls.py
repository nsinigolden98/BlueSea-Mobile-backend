from django.urls import path
from .views import CurrentUserView, CheckUsers

# Define the app namespace
app_name = 'user_preference'

urlpatterns = [
    path('user/', CurrentUserView.as_view(), name='user'),
    path('check/<str:email>/', CheckUsers.as_view(), name='check'),
]