from django.urls import path
from .views import CurrentUserView

# Define the app namespace
app_name = 'user_preference'

urlpatterns = [
    path('user/', CurrentUserView.as_view(), name='user'),
]