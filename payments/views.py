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
from .models import AirtimeTopUp, ElectricityPayment, JAMBRegistration, WAECRegitration, WAECResultChecker
from wallet.models import Wallet
from .vtpass import *

class AirtimeTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = AirtimeTopUpSerializer(data = request.data)
        
        if serializer.is_valid(raise_exception=True):
                serializer.save()
            
                with transaction.atomic():
                    request_id = generate_reference_id()
                    amount = int(serializer.data['amount'])
                    data = {
                        # "request_id": str(ref_id.reference_id).replace(" ",""),
                        "request_id": request_id,
                        "serviceID": serializer.data["network"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"]
                    }
                    user_wallet = request.user.wallet
                    # Wallet.debit(amount, ref_id)
                    buy_airtime_response = top_up(data)
                    if buy_airtime_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id)
                    
                    return Response(buy_airtime_response)


class ElectricityPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = ElectricityPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            with transaction.atomic():
                request_id = generate_reference_id()
                amount = int(serializer.data["amount"])
                data = {
                        "request_id": request_id,
                        "serviceID": serializer.data["biller_name"],
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": serializer.data["meter_type"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"]
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                electricity_response = top_up(data)
                if electricity_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=serializer.data["reference_id"])
                return Response(electricity_response)
                

class WAECRegitrationViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = WAECRegitrationSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            with transaction.atomic():
                request_id = generate_reference_id()
                amount = 14500
                data = {
                        "request_id": request_id,
                        "serviceID": "waec-registration",
                        "variation_code": "waec-registration",
                        "quantity" : 1,
                        "phone": serializer.data["phone_number"]
                    }
                # Wallet.debit(amount)
                user_wallet = request.user.wallet 
                registration_response = top_up(data)
                if registration_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(registration_response)
                

class WAECResultCheckerViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = WAECResultCheckerSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            with transaction.atomic():
                request_id = generate_reference_id()
                amount = 950
                data = {
                        "request_id": request_id,
                        "serviceID": "waec",
                        "variation_code": "waecdirect",
                        "quantity" : 1,
                        "phone": serializer.data["phone_number"]
                    }
                # Wallet.debit(amount)
                user_wallet = request.user.wallet

                registration_response = top_up(data)
                if registration_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(registration_response)
                

class JAMBRegistrationViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = JAMBRegistrationSerializer(data = request.data)
        
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            
            with transaction.atomic():
                request_id = generate_reference_id()
                amount = 7700 if serializer.data["exam_type"] == 'utme-mock' else 6200
                data = {
                        "request_id": request_id,
                        "serviceID": "jamb",
                        "variation_code": serializer.data["exam_type"],
                        "billerCode" : serializer.data["billerCode"],
                        "phone": serializer.data["phone_number"]
                    }
                # Wallet.debit(amount)
                user_wallet = request.user.wallet 
                jamb_registration_response = top_up(data)
                if jamb_registration_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(jamb_registration_response)
                