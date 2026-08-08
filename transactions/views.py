from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
import json
from decimal import Decimal
from rest_framework.views import APIView
from .models import WalletTransaction, FundWallet, Withdraw
from .serializers import WalletTransactionSerializer, WalletFundingSerializer, AccountNameSerializer, WithdrawSerializer, InitializeFundingSerializer, WithdrawRequestSerializer
from wallet.models import Wallet
from wallet.serializers import WalletSerializer
import uuid
from .paystack import checkout, get_account_name, initiate_transfer
from django.utils import timezone
from django.conf import settings
import hmac
import hashlib
import logging
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from drf_spectacular.types import OpenApiTypes
from .pagination import WalletTransactionPagination 
from notifications.utils import send_notification


logger = logging.getLogger(__name__)


class GetWalletTransaction(APIView):
    permission_classes = [IsAuthenticated]
    
    # Instantiate the paginator class for use in the get method
    paginator = WalletTransactionPagination() 

    @extend_schema(
        summary="Get wallet transactions",
        description="Retrieve all wallet transactions for the authenticated user, paginated.",
        responses={
            200: inline_serializer(
                "PaginatedWalletTransactions",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.URLField(allow_null=True),
                    "previous": serializers.URLField(allow_null=True),
                    "results": WalletTransactionSerializer(many=True),
                },
            ),
            404: OpenApiTypes.OBJECT,
        },
        tags=['Wallet & Transactions']
    )
    def get(self, request):
        user = request.user
        
        try:
            wallet = Wallet.objects.get(user=user)
            
            # 1. Get the full queryset, ordering is important!
            transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at') 
            
            # 2. Apply pagination to the queryset
            page = self.paginator.paginate_queryset(transactions, request, view=self)
            
            # 3. Serialize the paginated result (the 'page' object)
            serializer = WalletTransactionSerializer(page, many=True)
            
            # 4. Return the paginated response
            return self.paginator.get_paginated_response(serializer.data)
            
        except Wallet.DoesNotExist: 
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)


        
class InitializeFunding(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Initialize wallet funding",
        description="Initialize Paystack payment to fund user wallet (minimum: ₦100)",
        request=InitializeFundingSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Funding Request",
                value={"amount": "5000.00"},
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "success": True,
                    "authorization_url": "https://checkout.paystack.com/xyz",
                    "payment_reference": "BS-1234-abcd",
                    "amount": "5000.00",
                },
                response_only=True,
            ),
        ],
        tags=['Wallet & Transactions']
    )

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            amount = Decimal(str(data.get('amount')))

            if amount < Decimal('100.00'):
                return Response({"error": "Minimum funding amount is 100.00"}, status=status.HTTP_400_BAD_REQUEST)

            payment_reference = f"BS-{uuid.uuid4()}"

            # FundWallet.objects.create(
            #     user=request.user,
            #     amount=amount,
            #     payment_reference=payment_reference,
            #     status="PENDING"
            # )

            FundWallet.objects.create(
                user=request.user,
                amount=amount,
                payment_reference=payment_reference,
                status="PENDING"
            )

            payload = {
                "email": request.user.email,
                "amount": int(amount * 100),
                "reference": payment_reference,
                # "callback_url": callback_url
                "metadata": {
                    "user_id": request.user.id,
                    "payment_reference": payment_reference
                }
            }

            # success, result = checkout(payload)

            # if not success:
            #     return JsonResponse({
            #         "success": False,
            #         "error": result
            #     }, status=400)

            # return JsonResponse({
            #     "success": True,
            #     "authorization_url": result,
            #     "payment_reference": payment_reference,
            #     "amount": str(amount),
            # })

            success, authorization_url = checkout(payload)
            

            if not success:
                return Response({"success": False, "error": authorization_url}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"success": True, "authorization_url": authorization_url, "payment_reference": payment_reference, "amount": str(amount)}, status=status.HTTP_200_OK)
        
        except Exception as e:
            # print("InitializeFunding error:", str(e))
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# class PaymentWebhook(APIView):
#     """Handle Paystack payment webhook callbacks"""
    
#     def verify_paystack_signature(self, request):
#         """Verify that the webhook is from Paystack"""
#         paystack_signature = request.headers.get('X-Paystack-Signature')
#         if not paystack_signature:
#             return False

#         # Calculate hash using your secret key
#         hash = hmac.new(
#             settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
#             request.body,
#             hashlib.sha512
#         ).hexdigest()
        
#         return hash == paystack_signature

#     def post(self, request, *args, **kwargs):
#         """Handle payment gateway webhooks"""
#         try:
#             # Log the incoming webhook data
#             logger.info("Received webhook payload: %s", request.body.decode('utf-8'))

#             # Verify webhook signature
#             if not self.verify_paystack_signature(request):
#                 logger.error("Invalid Paystack signature")
#                 return Response(
#                     {"success": False, "error": "Invalid signature"},
#                     status=status.HTTP_401_UNAUTHORIZED
#                 )

#             # Parse webhook data
#             data = json.loads(request.body)
#             event = data.get('event')
#             logger.info("Processing webhook event: %s", event)

#             # Handle successful charge
#             if event == 'charge.success':
#                 payload = data.get('data', {})
#                 reference = payload.get('reference')
#                 # Ensure amount is converted to Decimal properly
#                 raw_amount = Decimal(str(payload.get('amount', '0')))
#                 amount = raw_amount / Decimal('100')  # Convert from kobo to naira
#                 gateway_reference = str(payload.get('id'))

#                 logger.info(
#                     "Processing successful charge - Reference: %s, Raw Amount: %s, Converted Amount: %s",
#                     reference, raw_amount, amount
#                 )

#                 try:
#                     funding_request = FundWallet.objects.select_for_update().get(
#                         user = request.user,
#                         payment_reference=reference,
#                         status='PENDING'
#                     )
                    
#                     logger.info(
#                         "Found pending funding request: Amount: %s, User: %s", 
#                         funding_request.amount, 
#                         funding_request.user.email if funding_request.user else 'None'
#                     )

#                     # Convert both amounts to Decimal for comparison
#                     request_amount = Decimal(str(funding_request.amount))
#                     webhook_amount = Decimal(str(amount))

#                     if abs(request_amount - webhook_amount) > Decimal('0.01'):
#                         logger.error(
#                             "Amount mismatch - Expected: %s, Got: %s",
#                             request_amount, webhook_amount
#                         )
#                         funding_request.status = 'FAILED'
#                         funding_request.save()
#                         return Response({
#                             "success": False,
#                             "error": f"Amount mismatch. Expected {request_amount}, got {webhook_amount}"
#                         }, status=status.HTTP_400_BAD_REQUEST)

#                     try:
#                         with transaction.atomic():
#                             # Update status to processing
#                             funding_request.status = 'PROCESSING'
#                             funding_request.save()

#                             # Fund the wallet
#                             WalletConfig.fund_wallet(
#                                 user=funding_request.user,
#                                 amount=webhook_amount,
#                                 payment_reference=reference,
#                                 gateway_reference=gateway_reference
#                             )
#                             funding_request.status = 'SUCCESS'
#                             funding_request.save()
                            
#                             logger.info("Wallet funded successfully")
#                             return Response({
#                                 "success": True,
#                                 "message": "Payment processed successfully"
#                             })

#                     except Exception as e:
#                         logger.error("Error funding wallet: %s", str(e), exc_info=True)
#                         funding_request.status = 'FAILED'
#                         funding_request.save()
#                         return Response({
#                             "success": False,
#                             "error": str(e)
#                         }, status=status.HTTP_400_BAD_REQUEST)

#                 except FundWallet.DoesNotExist:
#                     logger.error("Invalid payment reference: %s", reference)
#                     return Response({
#                         "success": False,
#                         "error": "Invalid payment reference"
#                     }, status=status.HTTP_404_NOT_FOUND)

#             # Return success for other events
#             return Response({"success": True})

#         except json.JSONDecodeError as e:
#             logger.error("Invalid JSON payload: %s", str(e))
#             return Response({
#                 "success": False,
#                 "error": "Invalid JSON payload"
#             }, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.error("Unexpected error in webhook handler: %s", str(e), exc_info=True)
#             return Response({
#                 "success": False,
#                 "error": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentWebhook(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    def verify_signature(self, request):
        signature = request.headers.get('X-Paystack-Signature')
        if not signature:
            return False
        
        hash = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()

        return hash == signature

    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        try:
            # logger.info("Received webhook payload: %s", request.body.decode('utf-8'))

            # verify signature
            if not self.verify_signature(request):
                logger.error("Invalid Paystack signature")
                return Response({"success": False, "error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)
            
            data = json.loads(request.body)
            event = data.get('event')
            # logger.info("Processing webhook event: %s", event)

            # handle successful charge
            if event == 'charge.success':
                payload = data.get('data', {})
                reference = payload.get('reference')
                raw_amount = Decimal(str(payload.get('amount', '0')))
                amount = raw_amount / Decimal('100')

                # logger.info("Processing successful charge - Reference: %s, Raw Amount: %s, Converted Amount: %s", 
                #           reference, raw_amount, amount)

                try:
                    with transaction.atomic():
                        # Get funding request with lock
                        funding_request = FundWallet.objects.select_for_update().get(
                            payment_reference=reference,
                            status='PENDING'
                        )
                        
                        # logger.info("Found pending funding request: Amount: %s, User: %s", 
                        #           funding_request.amount, 
                        #           funding_request.user.email if funding_request.user else 'None')

                        # Get wallet with lock
                        try:
                            wallet = Wallet.objects.select_for_update().get(user=funding_request.user)
                            logger.info("Found wallet for user: %s, Current balance: %s", 
                                      funding_request.user.email, wallet.balance)
                        except Wallet.DoesNotExist:
                            logger.error("Wallet not found for user: %s", funding_request.user.email)
                            funding_request.status = 'FAILED'
                            funding_request.save()
                            return Response({
                                "success": False, 
                                "error": "Wallet not found"
                            }, status=status.HTTP_404_NOT_FOUND)

                        request_amount = Decimal(str(funding_request.amount))
                        webhook_amount = Decimal(str(amount))

                        if abs(request_amount - webhook_amount) > Decimal('0.01'):
                            logger.error("Amount mismatch - Expected: %s, Got: %s", 
                                      request_amount, webhook_amount)
                            funding_request.status = 'FAILED'
                            funding_request.save()
                            return Response({
                                "success": False, 
                                "error": f"Amount mismatch. Expected {request_amount}, got {webhook_amount}"
                            }, status=status.HTTP_400_BAD_REQUEST)

                        try:
                            # Update status to processing
                            funding_request.status = 'PROCESSING'
                            funding_request.save()

                            # Update wallet balance directly
                            old_balance = wallet.balance
                            wallet.balance += webhook_amount
                            wallet.save(update_fields=['balance', 'updated_at'])
                            
                            # Create transaction record
                            WalletTransaction.objects.create(
                                wallet=wallet,
                                amount=webhook_amount,
                                transaction_type='CREDIT',
                                description="Wallet Funding",
                                reference=reference
                            )
                            
                            # Update funding request status
                            funding_request.status = 'COMPLETED'
                            funding_request.completed_at = timezone.now()
                            funding_request.save()
                            
                            # logger.info(
                            #     "Wallet funded successfully. Old balance: %s, New balance: %s", 
                            #     old_balance, wallet.balance
                            # )

                            try:
                                send_notification(
                                user=request.user,
                                title="Deposite To Bluesea Account",
                                message=f"Successful Deposite of ₦{webhook_amount}",
                                notification_type="Account Deposite",
                                email_subject="BlueSea - Deposite",
                            )
                            except Exception as e:
                                  logger.error(f"Error awarding bonus points: {str(e)}")
                            
                            return Response({
                                "success": True, 
                                "message": "Payment processed successfully",
                                "old_balance": str(old_balance),
                                "new_balance": str(wallet.balance)
                            })

                        except Exception as e:
                            # logger.error("Error updating wallet: %s", str(e), exc_info=True)
                            funding_request.status = 'FAILED'
                            funding_request.save()
                            return Response({
                                "success": False, 
                                "error": str(e)
                            }, status=status.HTTP_400_BAD_REQUEST)
                    
                except FundWallet.DoesNotExist:
                    # logger.error("Invalid payment reference: %s", reference)
                    return Response({
                        "success": False, 
                        "error": "Invalid payment reference"
                    }, status=status.HTTP_404_NOT_FOUND)
                
            return Response({"success": True})
                
        except Exception as e:
            # logger.error("Unexpected error in webhook handler: %s", str(e), exc_info=True)
            return Response({
                "success": False, 
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AccountNameView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Resolve account name",
        description="Verify a bank account number and retrieve the account holder's name via Paystack.",
        request=AccountNameSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Resolve Request",
                value={"account_number": "0123456789", "bank_code": "058"},
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={"success": True, "account_name": "JOHN DOE"},
                response_only=True,
            ),
            OpenApiExample(
                "Not Found Response",
                value={"success": False, "message": "Could not resolve account name"},
                response_only=True,
            ),
        ],
        tags=['Wallet & Transactions']
    )
    def post(self, request):
        serializer = AccountNameSerializer(data = request.data)
        if serializer.is_valid(raise_exception = True):
            with transaction.atomic():
                account_number = serializer.data['account_number']
                bank_code = serializer.data['bank_code']
                
                account_name = get_account_name(account_number, bank_code)

                if account_name["success"]:
                    return Response(account_name, status =status.HTTP_200_OK)

                else:
                    return Response(account_name, status= status.HTTP_404_NOT_FOUND)

        else:

            return Response(account_name, status= status.HTTP_400_BAD_REQUEST)


class WithdrawView(APIView):
    permission_classes =[IsAuthenticated]

    @extend_schema(
        summary="Withdraw funds",
        description="Withdraw funds from the user's wallet to a bank account. Requires a valid transaction PIN.",
        request=WithdrawRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Withdraw Request",
                value={
                    "amount": "5000.00",
                    "account_name": "JOHN DOE",
                    "account_number": "0123456789",
                    "bank_name": "GTBank",
                    "bank_code": "058",
                    "transaction_pin": "123456",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Paystack Transfer Response",
                value={
                    "status": True,
                    "message": "Transfer requires OTP to continue",
                    "data": {
                        "reference": "BS-1234-abcd",
                        "transfer_code": "TRF_xyz",
                        "amount": 500000,
                        "currency": "NGN",
                    },
                },
                response_only=True,
            ),
        ],
        tags=['Wallet & Transactions']
    )
    def post(self, request):

        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required', "state" :False}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first', "state": False}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN', "state": False}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            serializer = WithdrawSerializer(data = request.data)
            payment_reference = f"BS-{uuid.uuid4()}"
            
            
            
            if serializer.is_valid(raise_exception =True):
                
                withdraw_request = serializer.save(payment_reference = payment_reference)
                    
                
                account_number = serializer.data['account_number']
                bank_code = serializer.data['bank_code']
                amount = serializer.data['amount']
                account_name = serializer.data['account_name']
                bank_name = serializer.data['bank_name']             

                with transaction.atomic():
                                   
                    create_withdrawal = initiate_transfer(
                        account_number = account_number,
                        bank_code= bank_code,
                        amount_ngn = float(amount),
                        reference = payment_reference,
                         account_name= account_name,
                         )
                    
                    if create_withdrawal:
                        withdraw_request.status = "COMPLETED"
                        withdraw_request.completed_at = timezone.now()
                        withdraw_request.save()
                        # Withdraw.objects.create(
#                             account_number= account_number,
#                             account_name= account_name,
#                             bank_name= bank_name,
#                             bank_code= bank_code,
#                             payment_reference= payment_reference,
#                             completed_at= withdraw_request.completed_at,
#                             created_at= withdraw_request.created_at
#                         )
                        

                        # request.user.wallet.debit(amount= amount, description= f"Transfer ₦{amount} to {account_name}", reference= payment_reference)
# 
                        return Response(create_withdrawal, status = status.HTTP_200_OK)


                    else:
                        return Response({'error': 'An error during the transaction', "state": False,"message":create_withdrawal}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        except Exception as e:
            return Response({
                "state": False, 
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        