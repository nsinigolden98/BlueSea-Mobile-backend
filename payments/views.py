from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import ( 
    AirtimeTopUpSerializer, 
    JAMBRegistrationSerializer,
    WAECRegitrationSerializer,
    WAECResultCheckerSerializer,
    ElectricityPaymentSerializer,
    )
from wallet.models import Wallet
from .vtpass import top_up


class AirtimeTopUpViews(APIView):
    
    def post(self, request):
        serializer = AirtimeTopUpSerializer(data = request.data)
        
        if serializer.is_valid(raise_exception=True):
                serializer.save()
            
                with transaction.atomic():
                    amount = serializer.data['amount'] 
                    data = {
                        "request_id": serializer.data["reference_id"],
                        "serviceID": serializer.data["network"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"]
                    }
                    Wallet.debit(amount) 
                    buy_airtime_response = top_up(data)
                    return Response(buy_airtime_response )
                    
class ElectricityPaymentViews(APIView):
    def post(self, request):
        serializer = ElectricityPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            with transaction.atomic():
                amount = serializer.data["amount"]
                data = {
                        "request_id": serializer.data["reference_id"],
                        "serviceID": serializer.data["biller_name"],
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": serializer.data["meter_type"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"]
                    }
                Wallet.debit(amount) 
                electricity_response = top_up(data)
                return Response(electricity_response)
                
class WAECRegitrationViews(APIView):
    def post(self, request):
        serializer = WAECRegitrationSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            with transaction.atomic():
                amount = 14500
                data = {
                        "request_id": serializer.data["reference_id"],
                        "serviceID": "waec-registration",
                        "variation_code": "waec-registration",
                        "quantity" : 1,
                        "phone": serializer.data["phone_number"]
                    }
                Wallet.debit(amount) 
                registration_response = top_up(data)
                return Response(registration_response)
                
class WAECResultCheckerViews(APIView):
    def post(self, request):
        serializer = WAECResultCheckerSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            with transaction.atomic():
                amount = 950
                data = {
                        "request_id": serializer.data["reference_id"],
                        "serviceID": "waec",
                        "variation_code": "waecdirect",
                        "quantity" : 1,
                        "phone": serializer.data["phone_number"]
                    }
                Wallet.debit(amount) 
                registration_response = top_up(data)
                return Response(registration_response)
                
class JAMBRegistrationViews(APIView):                   
    def post(self, request):
        serializer = JAMBRegistrationSerializer(data = request.data)
        
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            
            with transaction.atomic():
                amount = 7700 if serializer.data["exam_type"] == 'utme-mock' else 6200
                data = {
                        "request_id": serializer.data["reference_id"],
                        "serviceID": "jamb",
                        "variation_code": serializer.data["exam_type"],
                        "billerCode" : serializer.data["billerCode"],
                        "phone": serializer.data["phone_number"]
                    }
                Wallet.debit(amount) 
                jamb_registration_response = top_up(data)
                return Response(jamb_registration_response)
                