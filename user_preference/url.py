from django.urls import path
from .views import UserPreferenceView

# Define the app namespace
app_name = 'preferences'

urlpatterns = [
    # Endpoint: GET, PUT, PATCH /api/preferences/settings/
    # This single URL handles retrieval (GET) and full/partial update (PUT/PATCH)
    path('theme/', UserPreferenceView.as_view(), name='theme'),
]