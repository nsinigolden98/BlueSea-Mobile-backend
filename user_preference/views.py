from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import CurrentUserSerializer, UpdateUserSerializer
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.models import Profile

class CurrentUserView(APIView):
    # Ensure only authenticated users can access this view
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Needed for file uploads
    
    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data, status= status.HTTP_200_OK)
       
    def patch(self, request):
    
        serializer  =  UpdateUserSerializer(request.user, data= request.data ,  partial = True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile image updated successfully",
                "image": serializer.data.get('image') 
            }, status=status.HTTP_200_OK)
            
        return Response({"message": "Update Unsuccessful.  Network Error", "state": False}, status=status.HTTP_400_BAD_REQUEST)

class CheckUsers(APIView):
    def get(self, request, email):
        check = Profile.objects.filter(email = email, email_verified=True ).first()
        try:
            if check:
                return Response({"state": True ,"message": "User is verified" },status=status.HTTP_200_OK)
            else:
                return Response({"state": False ,"message": "User is not verified" },status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"state": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
