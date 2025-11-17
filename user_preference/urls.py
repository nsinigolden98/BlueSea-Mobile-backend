from django.urls import path
from .views import CurrentUserView

# Define the app namespace
app_name = 'user_preference'

urlpatterns = [
    # Endpoint: GET, PUT, PATCH /api/preferences/settings/
    # This single URL handles retrieval (GET) and full/partial update (PUT/PATCH)
    path('user/', CurrentUserView.as_view(), name='user'),
]