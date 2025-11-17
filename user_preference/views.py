from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import CurrentUserSerializer

class CurrentUserView(APIView):
    # Ensure only authenticated users can access this view
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # request.user is automatically set to the authenticated User object
        # or an AnonymousUser object if not authenticated (which IsAuthenticated prevents)
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data)
        