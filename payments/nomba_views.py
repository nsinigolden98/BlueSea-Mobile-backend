import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import NombaDedicatedAccount, PaystackDedicatedAccount
from accounts.pin_security import verify_pin_with_lockout
from notifications.utils import send_notification
from transactions.nomba_gateway import transfer_to_bank

from .models import InternalTransfer, Withdrawal
from .serializers import (
    WithdrawalRequestSerializer,
    WithdrawalResponseSerializer,
    WithdrawalSerializer,
)
from .vtpass import generate_reference_id

User = get_user_model()
logger = logging.getLogger(__name__)


class NombaWithdrawalView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Withdrawal via Nomba",
        description=(
            "Withdraw wallet funds to a bank account via Nomba. Requires JWT auth, a set "
            "transaction PIN, and a minimum amount of ₦500. If `account_number` matches an "
            "active in-system Nomba or Paystack dedicated virtual account, it is routed as an "
            "instant internal transfer (InternalTransfer, transfer_method=dva; self-transfers "
            "rejected with 400) instead of Nomba. Otherwise a Withdrawal record "
            "(provider=nomba, status pending) is created and a Nomba parent-account bank "
            "transfer is initiated. Final status is reconciled via "
            "`POST /transactions/nomba/webhook/` (`payout_success` / `payout_refund`)."
        ),
        request=WithdrawalRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            201: WithdrawalResponseSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            429: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=["Nomba"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "account_name": "John Doe",
                    "account_number": "0123456789",
                    "amount": "5000.00",
                    "bank_code": "058",
                    "bank_name": "GTBank",
                    "transaction_pin": "encrypted_pin_string",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Internal Transfer (DVA match)",
                value={
                    "state": True,
                    "message": "Internal tranfer successful",
                    "withdrawal": {
                        "routed_to_internal": True,
                        "transfer_method": "dva",
                        "message": "Transfer successful",
                        "reference": "BS-INT-abc123",
                        "amount": "5000.00",
                        "recipient": "recipient@example.com",
                        "recipient_name": "Jane Doe",
                    },
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid PIN",
                value={"error": "Invalid transaction PIN", "success": False},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "PIN Locked",
                value={"error": "Too many attempts. Try again in 5 minutes."},
                response_only=True,
                status_codes=["429"],
            ),
            OpenApiExample(
                "Insufficient Funds",
                value={"error": "Insufficient funds", "success": False},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def post(self, request):
        serializer = WithdrawalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account_name = data["account_name"]
        account_number = data["account_number"]
        bank_code = data["bank_code"]
        bank_name = data["bank_name"]
        amount = data["amount"]
        transaction_pin = data["transaction_pin"]

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first", "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pin_result = verify_pin_with_lockout(request.user, transaction_pin)
        if pin_result.locked:
            retry_min = int(pin_result.retry_after // 60) + 1
            return Response(
                {"error": f"Too many attempts. Try again in {retry_min} minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if not pin_result.ok:
            return Response(
                {"error": "Invalid transaction PIN", "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # DVA routing: Nomba table first, then Paystack table (both rails live).
        dva_account_number = (account_number or "").strip()
        recipient = None
        nomba_dva = (
            NombaDedicatedAccount.objects.select_related("user")
            .filter(account_number=dva_account_number, active=True)
            .first()
        )
        if nomba_dva is not None:
            recipient = nomba_dva.user
        else:
            paystack_dva = (
                PaystackDedicatedAccount.objects.select_related("user")
                .filter(dva_account_number=dva_account_number, active=True)
                .first()
            )
            if paystack_dva is not None:
                recipient = paystack_dva.user
        if recipient is not None:
            if recipient.pk == request.user.pk:
                return Response(
                    {"error": "Cannot transfer to yourself", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                sender_wallet = request.user.wallet
            except Exception:
                return Response(
                    {"error": "Sender wallet not found", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                recipient_wallet = recipient.wallet
            except Exception:
                return Response(
                    {"error": "Recipient wallet not found", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if sender_wallet.balance < amount:
                return Response(
                    {"error": "Insufficient funds", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sender_reference = f"BS-INT-{generate_reference_id()}"
            recipient_reference = f"BS-INT-{generate_reference_id()}"
            try:
                transfer = InternalTransfer.objects.create(
                    reference_id=sender_reference,
                    user=request.user,
                    amount=amount,
                    recepiant_dva_account_number=dva_account_number,
                    recepiant_email=recipient.email,
                    recepiant_full_name=f"{recipient.surname} {recipient.other_names}".strip(),
                    transfer_method="dva",
                )
            except Exception as e:
                logger.error(f"Error creating DVA internal transfer record: {str(e)}")
                return Response(
                    {"success": False, "error": f"Transfer failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            try:
                with transaction.atomic():
                    sender_wallet.debit(
                        amount=amount,
                        description=f"Internal transfer to {recipient.email} ({dva_account_number})",
                        reference=sender_reference,
                    )
                    recipient_wallet.credit(
                        amount=amount,
                        description=f"Internal transfer from {request.user.email}",
                        reference=recipient_reference,
                    )
                    transfer.status = "successful"
                    transfer.completed_at = timezone.now()
                    transfer.save(update_fields=["status", "completed_at"])
                    try:
                        send_notification(
                            user=request.user,
                            title="Transfer Successful",
                            message=f"₦{amount} transferred to {recipient.email}",
                            notification_type="payment_success",
                            email_subject="BlueSea Mobile - Transfer Successful",
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification: {str(e)}")
                    try:
                        send_notification(
                            user=recipient,
                            title="Funds Received",
                            message=f"₦{amount} received from {request.user.email}",
                            notification_type="payment_success",
                            email_subject="BlueSea Mobile - Funds Received",
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification: {str(e)}")
                return Response(
                    {
                        "state": True,
                        "message": "Internal tranfer successful",
                        "withdrawal": {
                            "routed_to_internal": True,
                            "transfer_method": "dva",
                            "message": "Transfer successful",
                            "reference": sender_reference,
                            "amount": str(amount),
                            "recipient": recipient.email,
                            "recipient_name": transfer.recepiant_full_name,
                        },
                    },
                    status=status.HTTP_200_OK,
                )
            except ValueError as e:
                try:
                    transfer.status = "failed"
                    transfer.completed_at = timezone.now()
                    transfer.save(update_fields=["status", "completed_at"])
                except Exception:
                    pass
                if "Insufficient funds" in str(e):
                    return Response(
                        {"error": "Insufficient funds", "success": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return Response(
                    {"success": False, "error": f"Transfer failed: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                try:
                    transfer.status = "failed"
                    transfer.completed_at = timezone.now()
                    transfer.save(update_fields=["status", "completed_at"])
                except Exception:
                    pass
                return Response(
                    {"success": False, "error": f"Transfer failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        try:
            sender_wallet = request.user.wallet
        except Exception:
            return Response(
                {"error": "Wallet not found", "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if sender_wallet.balance < amount:
            return Response(
                {"error": "Insufficient funds", "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                reference_id = f"BS-WIT-{generate_reference_id()}"
                withdrawal = Withdrawal.objects.create(
                    user=request.user,
                    account_name=account_name,
                    account_number=account_number,
                    bank_code=bank_code,
                    bank_name=bank_name,
                    amount=amount,
                    payment_reference=reference_id,
                    status="pending",
                    provider="nomba",
                )

                try:
                    transfer_success, transfer_result = transfer_to_bank(
                        amount=amount,
                        account_number=account_number,
                        account_name=account_name,
                        bank_code=bank_code,
                        merchant_tx_ref=reference_id,
                        sender_name=f"{request.user.surname} {request.user.other_names}".strip()
                        or request.user.email,
                    )
                    if not transfer_success:
                        withdrawal.status = "failed"
                        withdrawal.completed_at = timezone.now()
                        withdrawal.save(update_fields=["status", "completed_at"])
                        logger.error(f"Nomba transfer failed: {transfer_result}")
                        raise Exception(f"Transfer failed: {transfer_result}")

                    withdrawal.transfer_code = str(
                        transfer_result.get("id", "")
                        if isinstance(transfer_result, dict)
                        else transfer_result
                    )
                    withdrawal.status = "successful"
                    withdrawal.completed_at = timezone.now()
                    withdrawal.save(
                        update_fields=["status", "transfer_code", "completed_at"]
                    )

                    sender_wallet.debit(
                        amount=amount,
                        description=f"Transfer to {account_name} ({account_number}) via Nomba",
                        reference=reference_id,
                    )

                    try:
                        send_notification(
                            user=request.user,
                            title="Transfer Successful",
                            message=(
                                f"₦{amount} transfer to {account_name} "
                                "received. It will be processed shortly."
                            ),
                            notification_type="payment",
                            email_subject="BlueSea Mobile- Transfer Successful",
                        )
                    except Exception as e:
                        logger.error(f"Error sending withdrawal notification: {str(e)}")

                    response_serializer = WithdrawalResponseSerializer(
                        {
                            "state": True,
                            "message": "Transfer successful",
                            "withdrawal": withdrawal,
                        }
                    )
                    return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    logger.error(f"Nomba auto-transfer error: {str(e)}")
                    return Response(
                        {
                            "state": False,
                            "message": "Invalid Request",
                            "withdrawal": WithdrawalSerializer(withdrawal).data,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except Exception as e:
            logger.error(f"Error processing Nomba withdrawal: {str(e)}")
            return Response(
                {"success": False, "error": f"Transfer failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
