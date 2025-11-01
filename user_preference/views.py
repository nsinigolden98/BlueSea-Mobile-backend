from rest_framework import generics, permissions
from .models import UserPreference
from .serializers import UserPreferenceSerializer

class UserPreferenceView(generics.RetrieveUpdateAPIView):

    serializer_class = UserPreferenceSerializer
    # Requires the user to be logged in to access
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):

        user = self.request.user
        preference, created = UserPreference.objects.get_or_create(user=user)
        
        return preference