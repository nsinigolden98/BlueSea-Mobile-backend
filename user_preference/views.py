from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import CurrentUserSerializer, UpdateUserSerializer
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

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