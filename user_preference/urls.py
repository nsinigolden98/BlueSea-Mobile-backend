from django.urls import path

from .views import CheckUser, CurrentUserView, GetUser

# Define the app namespace
app_name = 'user_preference'

urlpatterns = [
    path('user/', CurrentUserView.as_view(), name='user'),
    path('check/<str:email>/', CheckUser.as_view(), name='check'),
    path('get/<str:email>/', GetUser.as_view(), name='get-user'),
]