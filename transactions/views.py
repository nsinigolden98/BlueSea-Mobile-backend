from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from decimal import Decimal
from rest_framework.views import APIView
from .models import WalletTransaction, FundWallet
from .serializers import WalletTransactionSerializer, WalletFundingSerializer
from wallet.models import Wallet
from wallet.serializers import WalletSerializer
from .utils import WalletConfig
import uuid
from .paystack import checkout
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
import hmac
import hashlib
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


class GetWalletTransaction(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            wallet_balance = WalletConfig.transaction_history(user)
            return Response({"message": str(wallet_balance)}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InitializeFunding(APIView):
    permission_classes = [IsAuthenticated]

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
            print("InitializeFunding error:", str(e))
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentWebhook(APIView):
    """Handle Paystack payment webhook callbacks"""
    
    def verify_paystack_signature(self, request):
        """Verify that the webhook is from Paystack"""
        paystack_signature = request.headers.get('X-Paystack-Signature')
        if not paystack_signature:
            return False

        # Calculate hash using your secret key
        hash = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()
        
        return hash == paystack_signature

    def post(self, request, *args, **kwargs):
        """Handle payment gateway webhooks"""
        try:
            # Log the incoming webhook data
            logger.info("Received webhook payload: %s", request.body.decode('utf-8'))

            # Verify webhook signature
            if not self.verify_paystack_signature(request):
                logger.error("Invalid Paystack signature")
                return Response(
                    {"success": False, "error": "Invalid signature"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Parse webhook data
            data = json.loads(request.body)
            event = data.get('event')
            logger.info("Processing webhook event: %s", event)

            # Handle successful charge
            if event == 'charge.success':
                payload = data.get('data', {})
                reference = payload.get('reference')
                # Ensure amount is converted to Decimal properly
                raw_amount = Decimal(str(payload.get('amount', '0')))
                amount = raw_amount / Decimal('100')  # Convert from kobo to naira
                gateway_reference = str(payload.get('id'))

                logger.info(
                    "Processing successful charge - Reference: %s, Raw Amount: %s, Converted Amount: %s",
                    reference, raw_amount, amount
                )

                try:
                    funding_request = FundWallet.objects.select_for_update().get(
                        user = request.user,
                        payment_reference=reference,
                        status='PENDING'
                    )
                    
                    logger.info(
                        "Found pending funding request: Amount: %s, User: %s", 
                        funding_request.amount, 
                        funding_request.user.email if funding_request.user else 'None'
                    )

                    # Convert both amounts to Decimal for comparison
                    request_amount = Decimal(str(funding_request.amount))
                    webhook_amount = Decimal(str(amount))

                    if abs(request_amount - webhook_amount) > Decimal('0.01'):
                        logger.error(
                            "Amount mismatch - Expected: %s, Got: %s",
                            request_amount, webhook_amount
                        )
                        funding_request.status = 'FAILED'
                        funding_request.save()
                        return Response({
                            "success": False,
                            "error": f"Amount mismatch. Expected {request_amount}, got {webhook_amount}"
                        }, status=status.HTTP_400_BAD_REQUEST)

                    try:
                        with transaction.atomic():
                            # Update status to processing
                            funding_request.status = 'PROCESSING'
                            funding_request.save()

                            # Fund the wallet
                            WalletConfig.fund_wallet(
                                user=funding_request.user,
                                amount=webhook_amount,
                                payment_reference=reference,
                                gateway_reference=gateway_reference
                            )
                            funding_request.status = 'SUCCESS'
                            funding_request.save()
                            
                            logger.info("Wallet funded successfully")
                            return Response({
                                "success": True,
                                "message": "Payment processed successfully"
                            })

                    except Exception as e:
                        logger.error("Error funding wallet: %s", str(e), exc_info=True)
                        funding_request.status = 'FAILED'
                        funding_request.save()
                        return Response({
                            "success": False,
                            "error": str(e)
                        }, status=status.HTTP_400_BAD_REQUEST)

                except FundWallet.DoesNotExist:
                    logger.error("Invalid payment reference: %s", reference)
                    return Response({
                        "success": False,
                        "error": "Invalid payment reference"
                    }, status=status.HTTP_404_NOT_FOUND)

            # Return success for other events
            return Response({"success": True})

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON payload: %s", str(e))
            return Response({
                "success": False,
                "error": "Invalid JSON payload"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Unexpected error in webhook handler: %s", str(e), exc_info=True)
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)