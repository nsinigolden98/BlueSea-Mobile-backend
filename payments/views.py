from django.db import transaction
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import  AirtimeTopUpSerializer
from wallet.models import Wallet
#from .vtpass import buy_airtime


class AirtimeTopUpViews(APIView):
    def get(self, request):
        return Response("Hello World")
    
    def post(self, request):
        serializer = AirtimeTopUpSerializer(data = request.data)
        print(serializer)
        if serializer.is_valid():
            serializer.save()
            return Response({"data":serializer.data})
        else:   
            return Response({"error": serializer.errors})
        """
            try:
                with transaction.atomic():
                    #amount = serializer.data['amount'] 
                    data = {
                        "request_id": serializer.data["reference_id"],
                        "serviceID": serializer.data["network"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"]
                    }
                    #Wallet.debit(amount) 
                    #buy_airtime_response = buy_airtime(data)
                    #if  buy_airtime_response["code"] != "000":
                     #   return Response(buy_airtime_response["content"]["transaction"]["status"] )
                return Response(
                    "gebvg", 
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                print(str(e)) # This prints the error for debugging
                return Response(
                    {
                        "message": "Top Up Not Successful. An error occurred during the transfer.",
                        "state": "False"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )"""

            
