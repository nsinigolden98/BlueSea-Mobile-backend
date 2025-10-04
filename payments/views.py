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
    DSTVPaymentSerializer,
    GOTVPaymentSerializer,
    StartimesPaymentSerializer,
    ShowMaxPaymentSerializer,
    MTNDataTopUpSerializer,
    AirtelDataTopUpSerializer,
    GloDataTopUpSerializer,
    EtisalatDataTopUpSerializer,
    GroupPaymentSerializer,
    )
from .models import (
    AirtimeTopUp, 
    ElectricityPayment, 
    JAMBRegistration, 
    WAECRegitration, 
    WAECResultChecker
    )
from wallet.models import Wallet
from .vtpass import (
    generate_reference_id, 
    top_up,
    dstv_dict,
    gotv_dict,
    startimes_dict,
    showmax_dict,
    mtn_dict,
    airtel_dict,
    glo_dict,
    etisalat_dict,
    )
    
class GroupPaymentViews(APIView):
    pass
    """
    def post(request):
        serializer = GroupPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            """
            
    
class AirtimeTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = AirtimeTopUpSerializer(data = request.data)
        
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            
            with transaction.atomic():
                    amount = int(serializer.data['amount'])
                    data = {
                        "request_id": request_id,
                        "serviceID": serializer.data["network"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"]
                    }
                    user_wallet = request.user.wallet
                    #Wallet.debit(amount, ref_id)
                    buy_airtime_response = top_up(data)
                    if buy_airtime_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id)
                    
                    return Response(buy_airtime_response)

class MTNDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = MTNDataTopUpSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = mtn_dict[serializer.data["plan"]][1]
                variation_code = mtn_dict[serializer.data["plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "mtn-data",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class AirtelDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = AirtelDataTopUpSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = airtel_dict[serializer.data["plan"]][1]
                variation_code = airtel_dict[serializer.data["plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "airtel-data",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class GloDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = GloDataTopUpSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = glo_dict[serializer.data["plan"]][1]
                variation_code = glo_dict[serializer.data["plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "glo-data",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class EtisalatDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = EtisalatDataTopUpSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = etisalat_dict[serializer.data["plan"]][1]
                variation_code = etisalat_dict[serializer.data["plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "etisalat-data",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class DSTVPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = DSTVPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = dstv_dict[serializer.data["dstv_plan"]][1]
                variation_code = dstv_dict[serializer.data["dstv_plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "dstv",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                        "subscription_type": serializer.data["subscription_type"],
                        "quanity" : 1
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class GOTVPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = GOTVPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = gotv_dict[serializer.data["gotv_plan"]][1]
                variation_code = gotv_dict[serializer.data["gotv_plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "gotv",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                        "subscription_type": serializer.data["subscription_type"],
                        "quanity" : 1
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class StartimesPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = StartimesPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = startimes_dict[serializer.data["startimes_plan"]][1]
                variation_code = startimes_dict[serializer.data["startimes_plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "startimes",
                        "billerCode": serializer.data["billerCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class ShowMaxPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = ShowMaxPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
                amount = showmax_dict[serializer.data["showmax_plan"]][1]
                variation_code = showmax_dict[serializer.data["showmax_plan"]][0]
                data = {
                        "request_id": request_id,
                        "serviceID": "showmax",
                        "billerCode": serializer.data["phone_number"],
                        "variation_code": variation_code,
                        "amount": amount,
                    }
                # Wallet.debit(amount) 
                user_wallet = request.user.wallet

                subscription_response = top_up(data)
                if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(subscription_response)
                
class ElectricityPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = ElectricityPaymentSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
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
                    user_wallet.debit(amount=amount, reference=request_id)
                return Response(electricity_response)
                
class WAECRegitrationViews(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = WAECRegitrationSerializer(data = request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
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
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            with transaction.atomic():
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
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            
            with transaction.atomic():
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
 
 