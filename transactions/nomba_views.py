import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema
from nomba import NombaValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.utils import send_notification
from wallet.models import Wallet

from .models import FundWallet
from .nomba_gateway import (
    confirm_transaction,
    create_checkout_order,
    create_nomba_virtual_account,
    lookup_account_name,
)
from .serializers import (
    InitializeFundingSerializer,
    NombaAccountLookupSerializer,
    NombaDvaConfirmSerializer,
)

logger = logging.getLogger(__name__)


def _first_present(data, *keys):
    for key in keys:
        if isinstance(data, dict):
            val = data.get(key)
            if val not in (None, ""):
                return val
    return None


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


class NombaInitializeFunding(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Initialize wallet funding via Nomba",
        description=(
            "Create a Nomba hosted checkout order to fund the authenticated user's wallet "
            "(minimum: ₦100). Creates a FundWallet record with status PENDING and a "
            "reference like `BS-DEP-<uuid>`, then returns the hosted `checkout_url` for "
            "the user to complete payment. Completion is asynchronous: "
            "`POST /transactions/nomba/webhook/` handles `payment_success` (credits wallet, "
            "marks FundWallet COMPLETED) and `payment_failed` (marks FundWallet FAILED). "
            "Requires JWT auth."
        ),
        request=InitializeFundingSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
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
                    "checkout_url": "https://checkout.nomba.com/xyz",
                    "payment_reference": "BS-DEP-1234-abcd",
                    "amount": "5000.00",
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Checkout Failed",
                value={"success": False, "error": "Nomba error ..."},
                response_only=True,
                status_codes=["400"],
            ),
        ],
        tags=["Nomba"],
    )
    def post(self, request, *args, **kwargs):
        serializer = InitializeFundingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data["amount"]

        import uuid

        payment_reference = f"BS-DEP-{uuid.uuid4()}"
        fund = FundWallet.objects.create(
            user=request.user,
            amount=amount,
            payment_reference=payment_reference,
            status="PENDING",
        )

        success, result = create_checkout_order(
            order_reference=payment_reference,
            amount=amount,
            email=request.user.email,
        )
        if not success:
            fund.status = "FAILED"
            fund.save(update_fields=["status"])
            return Response(
                {"success": False, "error": result},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fund.gateway_reference = payment_reference
        fund.save(update_fields=["gateway_reference"])
        return Response(
            {
                "success": True,
                "checkout_url": result,
                "payment_reference": payment_reference,
                "amount": str(amount),
            },
            status=status.HTTP_200_OK,
        )


class NombaAccountNameView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Resolve account name via Nomba",
        description=(
            "Verify a bank account number and retrieve the account holder's name via "
            "Nomba bank lookup. Provide the 10-digit `account_number` and the Nomba "
            "`bank_code` (e.g. 058). Returns 200 with `account_name` on success, "
            "404 with `{\"success\": False, \"message\": ...}` when it cannot be resolved. "
            "Requires JWT auth."
        ),
        request=NombaAccountLookupSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
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
                status_codes=["200"],
            ),
            OpenApiExample(
                "Not Found",
                value={"success": False, "message": "Could not resolve account name"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
        tags=["Nomba"],
    )
    def post(self, request):
        serializer = NombaAccountLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = lookup_account_name(
            serializer.validated_data["account_number"],
            serializer.validated_data["bank_code"],
        )
        if result["success"]:
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_404_NOT_FOUND)


class NombaDvaAssignView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Assign Nomba dedicated virtual account",
        description=(
            "Create a Nomba dedicated virtual account (DVA) for the authenticated user. "
            "Idempotent: returns 200 with `already_exists: True` when the user already has one, "
            "otherwise creates one with account_ref `BS-NOMBA-DVA-{user.id}` and returns 201. "
            "Transfers to this account credit the owner's wallet via the Nomba webhook "
            "(`payment_success` DVA inflow). Sends a 'Virtual Account Ready' notification. "
            "Requires JWT auth; no request body."
        ),
        request=None,
        responses={
            200: OpenApiTypes.OBJECT,
            201: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Assigned",
                value={
                    "success": True,
                    "account_number": "9930000001",
                    "account_name": "John Doe",
                    "bank_name": "Nomba",
                    "account_ref": "BS-NOMBA-DVA-7",
                    "active": True,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Already Exists",
                value={
                    "already_exists": True,
                    "account_number": "9930000001",
                    "account_name": "John Doe",
                    "bank_name": "Nomba",
                    "account_ref": "BS-NOMBA-DVA-7",
                    "active": True,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
        tags=["Nomba"],
    )
    def post(self, request):
        from accounts.models import NombaDedicatedAccount

        existing = NombaDedicatedAccount.objects.filter(user=request.user).first()
        if existing:
            return Response(
                {
                    "already_exists": True,
                    "account_number": existing.account_number,
                    "account_name": existing.account_name,
                    "bank_name": existing.bank_name,
                    "account_ref": existing.account_ref,
                    "active": existing.active,
                },
                status=status.HTTP_200_OK,
            )

        full_name = f"{request.user.surname} {request.user.other_names}".strip() or request.user.email
        account_ref = f"BS-NOMBA-DVA-{request.user.id}"
        success, result = create_nomba_virtual_account(
            account_ref=account_ref, account_name=full_name
        )
        if not success:
            return Response(
                {"success": False, "error": result},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dva = NombaDedicatedAccount.objects.create(
            user=request.user,
            account_ref=account_ref,
            account_number=str(result.get("bankAccountNumber", "")),
            account_name=str(result.get("bankAccountName", full_name)),
            bank_name=str(result.get("bankName", "")),
            active=not bool(result.get("expired", False)),
            nomba_response=result,
        )
        try:
            send_notification(
                user=request.user,
                title="Virtual Account Ready",
                message=f"Your Nomba virtual account {dva.account_number} is ready to receive funds.",
                notification_type="wallet",
                email_subject="BlueSea Mobile - Virtual Account Ready",
            )
        except Exception as e:
            logger.warning(f"Nomba DVA notify failed for {request.user.email}: {e}")
        return Response(
            {
                "success": True,
                "account_number": dva.account_number,
                "account_name": dva.account_name,
                "bank_name": dva.bank_name,
                "account_ref": dva.account_ref,
                "active": dva.active,
            },
            status=status.HTTP_201_CREATED,
        )


class NombaDvaConfirmView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Confirm Nomba transaction by sessionId",
        description=(
            "Reconfirm a Nomba transaction status using its `sessionId` (used to follow up "
            "on pending DVA credits or checkout funding). Proxies Nomba's confirm-by-sessionId "
            "endpoint and returns the raw transaction object. Requires JWT auth."
        ),
        request=NombaDvaConfirmSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Confirm Request",
                value={"session_id": "1234567890abcdef"},
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={"success": True, "transaction": {}},
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Missing session_id",
                value={"error": "session_id is required"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
        tags=["Nomba"],
    )
    def post(self, request):
        serializer = NombaDvaConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = (serializer.validated_data.get("session_id") or "").strip()
        if not session_id:
            return Response(
                {"error": "session_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success, result = confirm_transaction(session_id)
        if not success:
            return Response(
                {"success": False, "error": result},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"success": True, "transaction": result},
            status=status.HTTP_200_OK,
        )


class NombaPaymentWebhook(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        from nomba import NombaValidationError, verify_webhook_request

        if len(request.body) > 1024 * 100:
            logger.warning("Nomba webhook payload too large %s", len(request.body))
            return Response({"success": True}, status=status.HTTP_200_OK)
        try:
            payload = verify_webhook_request(
                settings.NOMBA_SIGNATURE_KEY,
                body=request.body,
                headers=dict(request.headers),
            )
        except NombaValidationError:
            logger.error("Invalid Nomba webhook signature")
            return Response(
                {"success": False, "error": "Invalid signature"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(f"Nomba webhook verification error: {e}")
            return Response(
                {"success": False, "error": "Verification failed"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not isinstance(payload, dict):
            return Response({"success": True}, status=status.HTTP_200_OK)
        event_type = payload.get("event_type")
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        logger.info(f"Nomba webhook event={event_type}")

        try:
            if event_type == "payment_success":
                self._handle_payment_success(payload, data)
            elif event_type == "payment_failed":
                self._handle_payment_failed(payload, data)
            elif event_type == "payout_success":
                self._handle_payout_success(payload, data)
            elif event_type == "payout_refund":
                self._handle_payout_refund(payload, data)
            else:
                logger.info(f"Nomba webhook ignored event_type={event_type}")
        except Exception as e:
            logger.error(f"Nomba webhook handling error: {e}", exc_info=True)
        return Response({"success": True}, status=status.HTTP_200_OK)

    def _reference(self, payload, data):
        return _first_present(
            data,
            "orderReference",
            "merchantTxRef",
            "merchant_tx_ref",
            "reference",
            "sessionId",
            "session_id",
        ) or _first_present(payload, "orderReference", "reference", "sessionId")

    def _handle_payment_success(self, payload, data):
        from accounts.models import NombaDedicatedAccount
        from transactions.models import WalletTransaction

        reference = self._reference(payload, data)
        amount = _to_decimal(
            _first_present(data, "amount", "transactionAmount", "settledAmount")
        )

        # 1) Checkout funding: match FundWallet by our order reference.
        if reference:
            fund = FundWallet.objects.filter(payment_reference=reference).first()
            if fund is not None and fund.status != "COMPLETED" and amount is not None:
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(user=fund.user)
                    if not WalletTransaction.objects.filter(reference=reference).exists():
                        wallet.credit(
                            amount=amount,
                            description=f"Nomba funding {reference}",
                            reference=reference,
                        )
                    fund.status = "COMPLETED"
                    fund.completed_at = timezone.now()
                    fund.save(update_fields=["status", "completed_at"])
                try:
                    send_notification(
                        user=fund.user,
                        title="Wallet Funded",
                        message=f"₦{amount} received via Nomba. Your wallet has been credited.",
                        notification_type="payment_success",
                        email_subject="BlueSea Mobile - Wallet Funded",
                    )
                except Exception as e:
                    logger.warning(f"Nomba funding notify failed {reference}: {e}")
                return

        # 2) DVA inflow: match dedicated account by account number.
        acct_num = _first_present(
            data,
            "accountNumber",
            "receiverAccountNumber",
            "destinationAccountNumber",
            "bankAccountNumber",
        )
        if acct_num:
            dva = (
                NombaDedicatedAccount.objects.select_related("user")
                .filter(account_number=str(acct_num), active=True)
                .first()
            )
            if dva is not None and amount is not None:
                credit_ref = f"BS-NOMBA-DVA-{reference or _first_present(data, 'sessionId', 'session_id') or 'W'}"
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(user=dva.user)
                    if not WalletTransaction.objects.filter(reference=credit_ref).exists():
                        wallet.credit(
                            amount=amount,
                            description=f"Nomba DVA {dva.account_number}",
                            reference=credit_ref,
                        )
                try:
                    send_notification(
                        user=dva.user,
                        title="Funds Received",
                        message=f"₦{amount} received via Nomba DVA {dva.account_number}. Your wallet has been credited.",
                        notification_type="payment_success",
                        email_subject="BlueSea Mobile - Funds Received",
                    )
                except Exception as e:
                    logger.warning(f"Nomba DVA notify failed {credit_ref}: {e}")
                return
        logger.warning(f"Nomba payment_success matched nothing ref={reference} acct={acct_num}")

    def _handle_payment_failed(self, payload, data):
        reference = self._reference(payload, data)
        if not reference:
            return
        fund = FundWallet.objects.filter(payment_reference=reference).first()
        if fund is not None and fund.status == "PENDING":
            fund.status = "FAILED"
            fund.completed_at = timezone.now()
            fund.save(update_fields=["status", "completed_at"])
            try:
                send_notification(
                    user=fund.user,
                    title="Funding Failed",
                    message=f"Your Nomba wallet funding {reference} failed. No charge was made.",
                    notification_type="payment_failed",
                    email_subject="BlueSea Mobile - Funding Failed",
                )
            except Exception as e:
                logger.warning(f"Nomba failure notify failed {reference}: {e}")

    def _handle_payout_success(self, payload, data):
        from payments.models import Withdrawal

        reference = self._reference(payload, data)
        if not reference:
            return
        withdrawal = Withdrawal.objects.filter(
            payment_reference=reference, provider="nomba"
        ).first()
        if withdrawal is not None and withdrawal.status == "pending":
            withdrawal.status = "successful"
            withdrawal.completed_at = timezone.now()
            withdrawal.save(update_fields=["status", "completed_at"])

    def _handle_payout_refund(self, payload, data):
        from payments.models import Withdrawal
        from transactions.models import WalletTransaction

        reference = self._reference(payload, data)
        if not reference:
            return
        withdrawal = Withdrawal.objects.filter(
            payment_reference=reference, provider="nomba"
        ).first()
        if withdrawal is None:
            return
        if withdrawal.status != "successful":
            withdrawal.status = "failed"
            withdrawal.completed_at = timezone.now()
            withdrawal.save(update_fields=["status", "completed_at"])
            return
        reversal_ref = f"REV-{reference}"[:100]
        with transaction.atomic():
            try:
                wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
            except Wallet.DoesNotExist:
                return
            if WalletTransaction.objects.filter(reference=reversal_ref).exists():
                return
            wallet.credit(
                amount=withdrawal.amount,
                description=f"Refund for Nomba payout {reference}",
                reference=reversal_ref,
            )
            withdrawal.status = "failed"
            withdrawal.completed_at = timezone.now()
            withdrawal.save(update_fields=["status", "completed_at"])
