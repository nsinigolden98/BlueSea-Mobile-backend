from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound
from .models import UserPreference
from .serializers import UserPreferenceSerializer

class UserPreferenceView(generics.RetrieveUpdateDestroyAPIView):

    serializer_class = UserPreferenceSerializer
    # Only authenticated users can access their preferences
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if not user.is_authenticated or not user.is_active:
             raise NotFound("User is not authenticated.")
             
        try:
            preference = UserPreference.objects.get(user=user)
        except UserPreference.DoesNotExist:
       
            preference = UserPreference.objects.create(user=user)
            
        return preference
