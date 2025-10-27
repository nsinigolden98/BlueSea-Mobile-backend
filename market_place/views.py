from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import MarketPlace
from .serializers import MarketPlaceSerializer
from rest_framework.parsers import MultiPartParser, FormParser

class MarketPlaceView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, format=None):
        serializer = MarketPlaceSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, format=None):
        queryset = MarketPlace.objects.all()
        serializer = MarketPlaceSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
        