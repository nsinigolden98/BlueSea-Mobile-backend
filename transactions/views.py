from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
import json
from decimal import Decimal
from rest_framework.views import APIView
from .models import WalletTransaction, FundWallet
from .serializers import (
    WalletTransactionSerializer,
    WalletFundingSerializer,
    AccountNameSerializer,
    InitializeFundingSerializer,
)
from wallet.models import Wallet
from wallet.serializers import WalletSerializer
import uuid
from .paystack import checkout, get_account_name
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
        tags=["Wallet & Transactions"],
    )
    def get(self, request):
        user = request.user

        try:
            wallet = Wallet.objects.get(user=user)

            # 1. Get the full queryset, ordering is important!
            transactions = WalletTransaction.objects.filter(wallet=wallet).order_by(
                "-created_at"
            )

            # 2. Apply pagination to the queryset
            page = self.paginator.paginate_queryset(transactions, request, view=self)

            # 3. Serialize the paginated result (the 'page' object)
            serializer = WalletTransactionSerializer(page, many=True)

            # 4. Return the paginated response
            return self.paginator.get_paginated_response(serializer.data)

        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND
            )


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
        tags=["Wallet & Transactions"],
    )
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            amount = Decimal(str(data.get("amount")))

            if amount < Decimal("100.00"):
                return Response(
                    {"error": "Minimum funding amount is 100.00"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            payment_reference = f"BS-DEP-{uuid.uuid4()}"

            FundWallet.objects.create(
                user=request.user,
                amount=amount * Decimal("0.985"),
                payment_reference=payment_reference,
                status="PENDING",
            )

            payload = {
                "email": request.user.email,
                "amount": int(amount * 100),
                "reference": payment_reference,
                # "callback_url": callback_url
                "metadata": {
                    "user_id": request.user.id,
                    "payment_reference": payment_reference,
                },
            }

            success, authorization_url = checkout(payload)

            if not success:
                return Response(
                    {"success": False, "error": authorization_url},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    "success": True,
                    "authorization_url": authorization_url,
                    "payment_reference": payment_reference,
                    "amount": str(amount),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            # print("InitializeFunding error:", str(e))
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class PaymentWebhook(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def verify_signature(self, request):
        signature = request.headers.get("X-Paystack-Signature")
        if not signature:
            return False

        hash = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"), request.body, hashlib.sha512
        ).hexdigest()

        return hash == signature

    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        try:
            # logger.info("Received webhook payload: %s", request.body.decode('utf-8'))

            # verify signature
            if not self.verify_signature(request):
                logger.error("Invalid Paystack signature")
                return Response(
                    {"success": False, "error": "Invalid signature"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            data = json.loads(request.body)
            event = data.get("event")
            # logger.info("Processing webhook event: %s", event)

            # Handle Dedicated Virtual Account assignment webhooks per Paystack docs: https://paystack.com/docs/payments/dedicated-virtual-accounts/#handling-events
            if event in [
                "dedicatedaccount.assign.success",
                "dedicatedaccount.assign.failed",
                "customeridentification.success",
                "customeridentification.failed",
            ]:
                try:
                    from accounts.models import PaystackDedicatedAccount

                    payload_data = data.get("data", {})
                    # Per docs: DVA events contain customer, dedicated_account, etc.
                    # For dedicatedaccount.assign.success: data: {customer: {customer_code, id, ...}, dedicated_account: {account_number, account_name, bank: {name, slug, id}, id, active, ...}, ...}
                    # For customeridentification.success: data: {customer_id, customer_code, ...}
                    customer_code = None
                    dedicated = None
                    if isinstance(payload_data.get("customer"), dict):
                        customer_code = payload_data["customer"].get("customer_code")
                    elif payload_data.get("customer_code"):
                        customer_code = payload_data.get("customer_code")
                    if payload_data.get("dedicated_account"):
                        dedicated = payload_data.get("dedicated_account")
                    elif payload_data.get("account_number"):
                        dedicated = payload_data

                    if event == "dedicatedaccount.assign.success" and dedicated:
                        account_number = dedicated.get("account_number")
                        # Find DVA by customer_code or account_number
                        dva = None
                        if customer_code:
                            dva = PaystackDedicatedAccount.objects.filter(
                                customer_code=customer_code
                            ).first()
                        if not dva and account_number:
                            dva = PaystackDedicatedAccount.objects.filter(
                                account_number=account_number
                            ).first()
                        if dva:
                            dva.active = dedicated.get("active", True)
                            dva.paystack_response = payload_data
                            dva.save(
                                update_fields=[
                                    "active",
                                    "paystack_response",
                                    "updated_at",
                                ]
                            )
                            if not dva.user.has_DVA:
                                dva.user.has_DVA = True
                                dva.user.save(update_fields=["has_DVA"])
                            logger.info(
                                f"DVA webhook {event} updated {dva.account_number} for {dva.user.email}"
                            )
                            # Notify user that DVA is now active (credit-ready)
                            try:
                                send_notification(
                                    user=dva.user,
                                    title="Dedicated Account Active",
                                    message=f"Your Wema DVA {dva.account_number} is now active via webhook and ready to receive funds.",
                                    notification_type="dva_assigned",
                                    email_subject="BlueSea - DVA Active",
                                )
                            except Exception as e:
                                logger.warning(
                                    f"DVA webhook notify failed {event}: {e}"
                                )
                    elif event == "dedicatedaccount.assign.failed":
                        reason = (
                            payload_data.get("reason")
                            or data.get("reason")
                            or "Unknown"
                        )
                        logger.warning(
                            f"DVA assign failed: {reason} customer_code={customer_code} data={payload_data}"
                        )

                    if event in [
                        "customeridentification.success",
                        "customeridentification.failed",
                    ]:
                        logger.info(
                            f"Customer identification {event} for customer_code={customer_code}: {payload_data.get('reason', '')}"
                        )

                    return Response({"success": True})
                except Exception as e:
                    logger.error(
                        f"DVA webhook handling error {event}: {e}", exc_info=True
                    )
                    return Response({"success": True})

            # handle successful charge - includes DVA dedicated_account transfers per docs: https://paystack.com/docs/payments/dedicated-virtual-accounts/#requery
            if event == "charge.success":
                payload = data.get("data", {})
                reference = payload.get("reference")
                raw_amount = Decimal(str(payload.get("amount", "0")))
                amount = raw_amount / Decimal("100")
                auth = payload.get("authorization") or {}
                channel = auth.get("channel") or payload.get("channel") or ""
                is_dva_transfer =  channel == "dedicated_nuban"
                amount = amount * Decimal("0.99") if is_dva_transfer else amount * Decimal("0.985")

                # DVA dedicated_account transfer: local bank -> Wema DVA -> Paystack webhook -> wallet credit
                if is_dva_transfer:
                    try:
                        from accounts.models import PaystackDedicatedAccount

                        customer_code = None
                        if isinstance(payload.get("customer"), dict):
                            customer_code = payload["customer"].get("customer_code")
                        elif payload.get("customer_code"):
                            customer_code = payload.get("customer_code")

                        # Idempotent: if transaction already exists, ack
                        if WalletTransaction.objects.filter(
                            reference=reference
                        ).exists():
                            logger.info(
                                f"DVA webhook duplicate reference {reference} ignored"
                            )
                            return Response({"success": True})

                        dva = None
                        if customer_code:
                            dva = (
                                PaystackDedicatedAccount.objects.select_related("user")
                                .filter(customer_code=customer_code)
                                .first()
                            )
                        if not dva:
                            acct_num = (
                                auth.get("receiver_bank_account_number")
                                or auth.get("account_number")
                                or payload.get("receiver_bank_account_number")
                            )
                            if acct_num:
                                dva = (
                                    PaystackDedicatedAccount.objects.select_related(
                                        "user"
                                    )
                                    .filter(account_number=acct_num)
                                    .first()
                                )

                        if not dva:
                            logger.warning(
                                f"DVA charge.success no matching DVA customer_code={customer_code} acct={auth.get('receiver_bank_account_number')} ref={reference}"
                            )
                            return Response({"success": True})

                        # Ensure has_DVA true
                        if not dva.user.has_DVA:
                            dva.user.has_DVA = True
                            try:
                                dva.user.save(update_fields=["has_DVA"])
                            except Exception:
                                pass

                        with transaction.atomic():
                            if WalletTransaction.objects.filter(
                                reference=reference
                            ).exists():
                                return Response({"success": True})
                            wallet = Wallet.objects.select_for_update().get(
                                user=dva.user
                            )
                            # Use wallet.credit for atomic F() update + idempotency
                            wallet.credit(
                                amount=amount,
                                description=f"DVA Wema {dva.account_number} from {auth.get("sender_name")} {auth.get('sender_bank_name', '')} via {dva.bank_name}",
                                reference=reference,
                            )
                            logger.info(
                                f"DVA credited {amount} to {dva.user.email} ref={reference} account={dva.account_number}"
                            )
                            try:
                                sender = f'{auth.get("sender_bank_name")} in {auth.get("sender_name")}' 
                                send_notification(
                                    user=dva.user,
                                    title="Dedicated Virtual Account Deposite Received",
                                    message=f"₦{amount} received via Wema DVA {dva.account_number} from {sender} (ref {reference}) — your BlueSea wallet has been credited.",
                                    notification_type="payment_success",
                                    email_subject="BlueSea Mobile- Dedicated Virtual Account Deposite Received",
                                )
                            except Exception as e:
                                logger.warning(f"DVA notify failed {reference}: {e}")
                            # Also push real-time update via WebSocket if needed (wallet balance)
                            try:
                                from channels.layers import get_channel_layer
                                from asgiref.sync import async_to_sync

                                channel_layer = get_channel_layer()
                                if channel_layer:
                                    async_to_sync(channel_layer.group_send)(
                                        f"wallet_user_{dva.user.id}",
                                        {
                                            "type": "wallet_update",
                                            "amount": str(amount),
                                            "reference": reference,
                                            "account_number": dva.account_number,
                                        },
                                    )
                            except Exception:
                                pass
                        return Response(
                            {"success": True, "message": "DVA transfer credited"}
                        )
                    except Wallet.DoesNotExist:
                        logger.error(f"DVA wallet not found for reference {reference}")
                        return Response(
                            {"success": False, "error": "Wallet not found"},
                            status=status.HTTP_404_NOT_FOUND,
                        )
                    except Exception as e:
                        logger.error(
                            f"DVA webhook error {reference}: {e}", exc_info=True
                        )
                        return Response(
                            {"success": False, "error": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                # logger.info("Processing successful charge - Reference: %s, Raw Amount: %s, Converted Amount: %s",
                #           reference, raw_amount, amount)

                try:
                    with transaction.atomic():
                        # Get funding request with lock
                        funding_request = FundWallet.objects.select_for_update().get(
                            payment_reference=reference, status="PENDING"
                        )

                        # logger.info("Found pending funding request: Amount: %s, User: %s",
                        #           funding_request.amount,
                        #           funding_request.user.email if funding_request.user else 'None')

                        # Get wallet with lock
                        try:
                            wallet = Wallet.objects.select_for_update().get(
                                user=funding_request.user
                            )
                            logger.info(
                                "Found wallet for user: %s, Current balance: %s",
                                funding_request.user.email,
                                wallet.balance,
                            )
                        except Wallet.DoesNotExist:
                            logger.error(
                                "Wallet not found for user: %s",
                                funding_request.user.email,
                            )
                            funding_request.status = "FAILED"
                            funding_request.save()
                            return Response(
                                {"success": False, "error": "Wallet not found"},
                                status=status.HTTP_404_NOT_FOUND,
                            )

                        request_amount = Decimal(str(funding_request.amount))
                        webhook_amount = Decimal(str(amount))

                        if abs(request_amount - webhook_amount) > Decimal("0.01"):
                            logger.error(
                                "Amount mismatch - Expected: %s, Got: %s",
                                request_amount,
                                webhook_amount,
                            )
                            funding_request.status = "FAILED"
                            funding_request.save()
                            return Response(
                                {
                                    "success": False,
                                    "error": f"Amount mismatch. Expected {request_amount}, got {webhook_amount}",
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        try:
                            # Update status to processing
                            funding_request.status = "PROCESSING"
                            funding_request.save()

                            # Update wallet balance directly
                            old_balance = wallet.balance
                            wallet.balance += webhook_amount
                            wallet.save(update_fields=["balance", "updated_at"])

                            # Create transaction record
                            WalletTransaction.objects.create(
                                wallet=wallet,
                                amount=webhook_amount,
                                transaction_type="CREDIT",
                                description="Wallet Funding",
                                reference=reference,
                            )

                            # Update funding request status
                            funding_request.status = "COMPLETED"
                            funding_request.completed_at = timezone.now()
                            funding_request.save()

                            # logger.info(
                            #     "Wallet funded successfully. Old balance: %s, New balance: %s",
                            #     old_balance, wallet.balance
                            # )

                            try:
                                send_notification(
                                    user=funding_request.user,
                                    title="Deposite To Bluesea Account",
                                    message=f"Successful Deposite of ₦{webhook_amount}",
                                    notification_type="payment_success",
                                    email_subject="BlueSea Mobile - Checkout Deposite",
                                )
                            except Exception as e:
                                logger.error(f"Error awarding bonus points: {str(e)}")

                            return Response(
                                {
                                    "success": True,
                                    "message": "Payment processed successfully",
                                    "old_balance": str(old_balance),
                                    "new_balance": str(wallet.balance),
                                }
                            )

                        except Exception as e:
                            # logger.error("Error updating wallet: %s", str(e), exc_info=True)
                            funding_request.status = "FAILED"
                            funding_request.save()
                            return Response(
                                {"success": False, "error": str(e)},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                except FundWallet.DoesNotExist:
                    # logger.error("Invalid payment reference: %s", reference)
                    return Response(
                        {"success": False, "error": "Invalid payment reference"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            return Response({"success": True})

        except Exception as e:
            # logger.error("Unexpected error in webhook handler: %s", str(e), exc_info=True)
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DvaRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Requery Wema DVA for pending transfers",
        description="Triggers Paystack requery for dedicated_account per docs: GET https://api.paystack.co/dedicated_account/requery?account_number={account_number}&provider_slug=wema-bank&date=YYYY-MM-DD. No reference needed (user's local bank reference unknown). Paystack will send webhook charge.success with dedicated_account channel if pending transactions found. Limited to once every 10 minutes per Paystack. Handles Paystack responses per docs.",
        request=inline_serializer(
            name="DvaRefreshRequest",
            fields={
                "date": serializers.CharField(
                    required=False,
                    help_text="Date transfer was made YYYY-MM-DD, defaults to today",
                ),
            },
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=["Wallet & Transactions"],
        examples=[
            OpenApiExample("Refresh Request", value={}, request_only=True),
            OpenApiExample(
                "Refresh with date", value={"date": "2026-09-01"}, request_only=True
            ),
            OpenApiExample(
                "Success",
                value={
                    "status": True,
                    "message": "We are checking the status of your transfer. We will send you a notification once it is confirmed",
                    "account_number": "0123456789",
                    "provider_slug": "wema-bank",
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        try:
            from accounts.models import PaystackDedicatedAccount
            import requests as req_lib
            from django.core.cache import cache

            dva = PaystackDedicatedAccount.objects.filter(user=request.user).first()
            if not dva:
                return Response(
                    {"error": "No DVA assigned. POST /account/dva/assign first."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Enforce Paystack 10-min per-DVA limit via cache
            cache_key = f"dva_requery:{dva.account_number}"
            if cache.get(cache_key):
                return Response(
                    {
                        "error": "Requery allowed once every 10 minutes",
                        "retry_after": 600,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            date_str = request.data.get("date")
            if date_str:
                try:
                    from datetime import datetime

                    datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    return Response(
                        {"error": "date must be YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                from django.utils import timezone

                date_str = timezone.now().date().isoformat()

            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            }
            params = {
                "account_number": dva.account_number,
                "provider_slug": "wema-bank",
                "date": date_str,
            }
            # Per Paystack docs: GET /dedicated_account/requery?account_number={accountNumber}&provider_slug={provider_slug}&date={yyyy-mm-dd}
            # Handle Paystack responses per docs: {status: true, message: "We are checking..."} on success; {status: false, message: "..."} on failure or too frequent
            try:
                r = req_lib.get(
                    "https://api.paystack.co/dedicated_account/requery",
                    params=params,
                    headers=headers,
                    timeout=(3, 10),
                )
            except req_lib.RequestException as e:
                logger.error(f"DVA requery network error for {request.user.email}: {e}")
                return Response(
                    {"error": "Unable to contact Paystack, try again"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            try:
                j = r.json()
            except Exception:
                logger.error(
                    f"DVA requery non-JSON for {request.user.email}: {r.text[:500]}"
                )
                return Response(
                    {"error": "Invalid response from Paystack"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            status_ok = j.get("status") is True
            message = j.get("message", "")
            if not status_ok:
                # Per docs: if requery too frequent, status false, message contains "10 minutes" or similar
                if "10 minutes" in message or "10 minute" in message.lower():
                    cache.set(cache_key, 1, 600)
                    return Response(
                        {
                            "error": message,
                            "paystack_status": j.get("status"),
                            "paystack_message": message,
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                logger.warning(f"DVA requery failed for {request.user.email}: {j}")
                return Response(
                    {
                        "error": message or "Failed to requery dedicated account",
                        "paystack_status": j.get("status"),
                        "paystack_message": message,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cache.set(cache_key, 1, 600)
            logger.info(
                f"DVA requery success for {request.user.email} account {dva.account_number} date {date_str}: {j}"
            )
            # Per docs, success means Paystack will send webhook charge.success with dedicated_account channel if pending transactions found
            return Response(
                {
                    "status": j.get("status"),
                    "message": message,
                    "account_number": dva.account_number,
                    "provider_slug": "wema-bank",
                    "date": date_str,
                    "requery": True,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"DVA refresh error: {e}", exc_info=True)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
        tags=["Wallet & Transactions"],
    )
    def post(self, request):
        serializer = AccountNameSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            with transaction.atomic():
                account_number = serializer.data["account_number"]
                bank_code = serializer.data["bank_code"]

                account_name = get_account_name(account_number, bank_code)

                if account_name["success"]:
                    return Response(account_name, status=status.HTTP_200_OK)

                else:
                    return Response(account_name, status=status.HTTP_404_NOT_FOUND)

        else:
            return Response(account_name, status=status.HTTP_400_BAD_REQUEST)
