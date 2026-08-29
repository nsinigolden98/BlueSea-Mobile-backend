import logging
import uuid
from decimal import Decimal
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from accounts.pin_security import verify_pin_with_lockout

User = get_user_model()
logger = logging.getLogger(__name__)

from group_payment.models import Group, GroupMember
from .models import GroupPayment, GroupPaymentContribution, Withdrawal
from transactions.models import WalletTransaction
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
    Airtime2CashSerializer,
    ElectricityPaymentCustomerSerializer,
    WithdrawalRequestSerializer,
    WithdrawalResponseSerializer,
)

from notifications.utils import (
    send_notification,
    contribution_notification,
    group_payment_success,
    group_payment_failed,
)
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
    get_customer,
    get_receipt,
)

from bluesea_mobile.utils import InsufficientFundsException, VTUAPIException
from bonus.utils import (
    award_daily_login_bonus,
    award_points,
    award_referral_bonus,
    award_vtu_purchase_points,
    user_points_summary,
    redeem_points,
)
from bonus.models import Referral, BonusCampaign, BonusHistory, BonusPoint
import logging
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


logger = logging.getLogger(__name__)


def get_payment_description(
    payment_type,
    network=None,
    phone=None,
    plan=None,
    amount=0,
    meter_number=None,
    biller_name=None,
    meter_type=None,
    exam_type=None,
    disco=None,
):
    phone_last4 = phone[-4:] if phone and len(phone) >= 4 else phone

    descriptions = {
        "airtime": {
            "full": f"AIRTIME: {network.upper() if network else ''} {phone_last4} - ₦{amount}",
            "short": f"Airtime - {network.upper() if network else ''}",
        },
        "data": {
            "full": f"DATA: {network.upper() if network else ''} {phone_last4} - {plan} - ₦{amount}",
            "short": f"Data - {network.upper() if network else ''}",
        },
        "dstv": {
            "full": f"DSTV: {phone_last4} - {plan} - ₦{amount}",
            "short": "DSTV",
        },
        "gotv": {
            "full": f"GOTV: {phone_last4} - {plan} - ₦{amount}",
            "short": "GOTV",
        },
        "startimes": {
            "full": f"STARTIMES: {phone_last4} - {plan} - ₦{amount}",
            "short": "Startimes",
        },
        "showmax": {
            "full": f"SHOWMAX: {phone_last4} - {plan} - ₦{amount}",
            "short": "Showmax",
        },
        "electricity": {
            "full": f"ELECTRICITY: {biller_name.replace('-', ' ').title() if biller_name else ''} {meter_type.capitalize() if meter_type else ''} {meter_number[-4:] if meter_number else ''} - ₦{amount}",
            "short": f"Electricity - {biller_name.replace('-', ' ').title() if biller_name else ''}",
        },
        "waec-registration": {
            "full": f"WAEC Registration - ₦{amount}",
            "short": "WAEC Registration",
        },
        "waec-result": {
            "full": f"WAEC Result Checker - ₦{amount}",
            "short": "WAEC Result",
        },
        "jamb": {
            "full": f"JAMB {'UTME Mock' if exam_type == 'utme-mock' else 'UTME'} - ₦{amount}",
            "short": "JAMB Registration",
        },
    }

    return descriptions.get(
        payment_type,
        {"full": f"{payment_type.title()} - ₦{amount}", "short": payment_type.title()},
    )


def process_payment(request, amount, service_data, service_name, description=None):
    """
    Helper function to process payments consistently.
    Returns (response, success) tuple.
    """
    user_wallet = request.user.wallet

    # Check balance first
    if user_wallet.balance < amount:
        return {"error": "Insufficient Funds", "success": False}, False

    # Call VTU API
    response = top_up(service_data)

    if response.get("response_description") == "TRANSACTION SUCCESSFUL":
        # Debit wallet
        user_wallet.debit(
            amount=amount,
            reference=service_data.get("request_id"),
            description=description or f"{service_name} Payment",
        )

        # Award bonus points
        try:
            award_vtu_purchase_points(
                user=request.user,
                purchase_amount=amount,
                reference=service_data.get("request_id"),
            )

            # Check for referral bonus
            try:
                referral = Referral.objects.get(
                    referred_user=request.user,
                    status="pending",
                    first_transaction_completed=False,
                )
                referral.first_transaction_completed = True
                referral.save()
                award_referral_bonus(referral.referrer, request.user)
            except Referral.DoesNotExist:
                pass
        except Exception as e:
            logger.error(f"Error awarding bonus points: {str(e)}")

        return response, True

    return response, False


class Airtime2CashViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Convert airtime to cash",
        description="Convert airtime to wallet cash balance. Requires JWT; validates PIN and wallet.",
        request=Airtime2CashSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={"amount": 100, "network": "mtn", "phone_number": "08012345678"},
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "message": "Airtime converted to wallet balance",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = Airtime2CashSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id=request_id, user=request.user)

            with transaction.atomic():
                amount = int(serializer.data["amount"])

                user_data = {
                    "apikey": "",
                    "serviceName": "Airtime2Cash",
                    "network": serializer.data["network"],
                }

                sitephone = top_up2(user_data, "merchant-verify")
                if sitephone != "Unavailable":
                    user_data = {
                        "apikey": "",
                        "network": serializer.data["network"],
                        "sender": "",
                        "sendernumber": serializer.data["phone_number"],
                        "amount": amount,
                        "ref": request_id,
                        "sitephone": sitephone,
                    }

                    topup_response = top_up2(user_data, "airtime2cash")

                    if topup_response.get("success"):
                        user_wallet = request.user.wallet
                        user_wallet.credit(amount=amount, reference=request_id)

                        try:
                            send_notification(
                                user=request.user,
                                title="Airtime Converted",
                                message=f"₦{amount} converted to cash successfully",
                                notification_type="payment_success",
                                email_subject="BlueSea - Airtime Converted",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                        return Response(
                            {
                                "success": True,
                                "message": "Airtime converted successfully",
                            },
                            status=status.HTTP_200_OK,
                        )

                    return Response(
                        {"success": False, "error": "Conversion failed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                return Response(
                    {"success": False, "error": "Service unavailable"},
                    status=status.HTTP_400_BAD_REQUEST,
                )


class GroupPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create group payment",
        description="Initiate a payment on behalf of a group (airtime, data, electricity, etc.). Requires JWT and group-admin role; splits the total across members per split_type. Wallet debited on success.",
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Group Airtime Payment",
                value={
                    "group_id": 1,
                    "payment_type": "airtime",
                    "total_amount": "1000.00",
                    "service_details": {
                        "network": "mtn",
                        "phone_number": "08012345678",
                    },
                    "split_type": "equal",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "contributions": [],
                    "created_at": "2026-08-20T00:00:00Z",
                    "group": 1,
                    "group_name": "Family Group",
                    "id": 1,
                    "initiated_by": 1,
                    "initiated_by_name": "Jane Doe",
                    "payment_type": "airtime",
                    "service_details": {
                        "network": "mtn",
                        "phone_number": "08012345678",
                    },
                    "status": "completed",
                    "total_amount": "1000.00",
                    "updated_at": "2026-08-20T00:00:00Z",
                    "vtu_reference": "VTU-20260820ABCD",
                },
                response_only=True,
            ),
        ],
        tags=["Payments"],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
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
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        group_id = request.data.get("group_id")
        payment_type = request.data.get("payment_type")
        total_amount = Decimal(str(request.data.get("total_amount")))
        service_details = request.data.get("service_details")
        split_type = request.data.get("split_type", "equal")
        custom_splits = request.data.get("custom_splits", {})

        group = get_object_or_404(Group, id=group_id)

        # Check if user is admin/owner
        is_admin = GroupMember.objects.filter(
            group=group, user=request.user, role__in=["admin", "owner"]
        ).exists()

        if not is_admin:
            return Response(
                {"error": "Only group admins can initiate payments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        members = GroupMember.objects.filter(group=group).select_related(
            "user", "user__wallet"
        )

        if members.count() == 0:
            return Response(
                {"error": "No active members in group"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate split amounts
        member_amounts = self._calculate_splits(
            members, total_amount, split_type, custom_splits
        )

        try:
            with transaction.atomic():
                group_payment = GroupPayment.objects.create(
                    group=group,
                    initiated_by=request.user,
                    payment_type=payment_type,
                    total_amount=total_amount,
                    service_details=service_details,
                    status="processing",
                )

                # Process each member's contribution
                for member in members:
                    amount = member_amounts.get(member)
                    wallet = member.user.wallet

                    if wallet.balance < amount:
                        raise InsufficientFundsException(
                            f"Insufficient funds for {member.user.email}"
                        )

                    # Create UNIQUE reference for each member's contribution
                    unique_reference = (
                        f"GP-{group_payment.id}-{member.user.id}-{uuid.uuid4().hex[:8]}"
                    )

                    # Debit wallet with unique reference
                    wallet.debit(
                        amount=amount,
                        description=f"Group payment contribution - {payment_type}",
                        reference=unique_reference,
                    )

                    # Create contribution record
                    GroupPaymentContribution.objects.create(
                        group_payment=group_payment,
                        member=member,
                        amount=amount,
                        status="completed",
                    )

                    # Send notification
                    try:
                        contribution_notification(
                            member=member,
                            amount=amount,
                            group_name=group.name,
                            payment_type=payment_type,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to send notification to {member.user.email}: {str(e)}"
                        )

                # All debits successful, now call VTU API
                vtu_response = self.vtu_api(payment_type, service_details, total_amount)

                if vtu_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    group_payment.status = "completed"
                    group_payment.vtu_reference = vtu_response.get(
                        "requestId", vtu_response.get("reference")
                    )
                    group_payment.save()

                    # Notify all members of success
                    for member in members:
                        try:
                            group_payment_success(
                                member=member,
                                amount=member_amounts.get(member),
                                group_name=group.name,
                                payment_type=payment_type,
                                vtu_reference=vtu_response.get("requestId"),
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to send success notification: {str(e)}"
                            )

                    return Response(
                        {
                            "success": True,
                            "message": "Group payment completed successfully",
                            "payment_id": group_payment.id,
                            "vtu_reference": group_payment.vtu_reference,
                            "total_amount": str(total_amount),
                            "member_contributions": {
                                member.user.email: str(member_amounts.get(member))
                                for member in members
                            },
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    # VTU API failed
                    group_payment.status = "failed"
                    group_payment.save()

                    # Reverse all debits by crediting back
                    for member in members:
                        amount = member_amounts.get(member)
                        wallet = member.user.wallet
                        reversal_reference = f"REV-{group_payment.id}-{member.user.id}-{uuid.uuid4().hex[:8]}"

                        wallet.credit(
                            amount=amount,
                            description=f"Reversal - Group payment failed",
                            reference=reversal_reference,
                        )

                    return Response(
                        {
                            "success": False,
                            "error": f"VTU service failed: {vtu_response.get('response_description', 'Unknown error')}. All debits have been reversed.",
                            "payment_id": group_payment.id,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        except InsufficientFundsException as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Group payment error: {str(e)}", exc_info=True)

            # Attempt to notify members of failure
            for member in members:
                try:
                    group_payment_failed(
                        member=member,
                        amount=member_amounts.get(member, 0),
                        group_name=group.name,
                        payment_type=payment_type,
                        reason=str(e),
                    )
                except Exception as notif_error:
                    logger.warning(
                        f"Failed to send failure notification: {str(notif_error)}"
                    )

            return Response(
                {
                    "success": False,
                    "error": f"Payment failed: {str(e)}. All debits have been reversed.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _calculate_splits(self, members, total_amount, split_type, custom_splits):
        member_amounts = {}

        if split_type == "equal":
            amount_per_member = total_amount / members.count()
            for member in members:
                member_amounts[member] = amount_per_member

        elif split_type == "percentage":
            for member in members:
                percentage = Decimal(str(custom_splits.get(str(member.user.id), 0)))
                member_amounts[member] = (total_amount * percentage) / 100

        return member_amounts

    def vtu_api(self, payment_type, service_details, amount):
        request_id = generate_reference_id()

        if payment_type == "airtime":
            with transaction.atomic():
                airtime_amount = int(amount)
                details = {
                    "request_id": request_id,
                    "serviceID": service_details.get("network"),
                    "amount": airtime_amount,
                    "phone": service_details.get("phone_number"),
                }
            subscription_response = top_up(details)
            return subscription_response

        elif payment_type == "data":
            if service_details.get("network") == "mtn":
                with transaction.atomic():
                    variation_code = mtn_dict[service_details.get("plan_id")][0]
                    amount = mtn_dict[service_details.get("plan_id")][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "mtn-data",
                        "billersCode": service_details.get("billersCode"),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get("phone_number"),
                    }
                subscription_response = top_up(details)
                return subscription_response
            elif service_details.get("network") == "airtel":
                with transaction.atomic():
                    variation_code = airtel_dict[service_details.get("plan_id")][0]
                    amount = airtel_dict[service_details.get("plan_id")][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "airtel-data",
                        "billersCode": service_details.get("billersCode"),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get("phone_number"),
                    }
                subscription_response = top_up(details)
                return subscription_response

            elif service_details.get("network") == "glo":
                with transaction.atomic():
                    variation_code = glo_dict[service_details.get("plan_id")][0]
                    amount = glo_dict[service_details.get("plan_id")][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "glo-data",
                        "billersCode": service_details.get("billersCode"),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get("phone_number"),
                    }
                subscription_response = top_up(details)
                return subscription_response

            elif service_details.get("network") == "etisalat":
                with transaction.atomic():
                    variation_code = etisalat_dict[service_details.get("plan_id")][0]
                    amount = etisalat_dict[service_details.get("plan_id")][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "etisalat-data",
                        "billersCode": service_details.get("billersCode"),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get("phone_number"),
                    }

        elif payment_type == "electricity":
            # return vtu_service.purchase_electricity(
            #     meter_number=service_details.get('meter_number'),
            #     amount=amount,
            #     disco=service_details.get('disco')
            # )

            with transaction.atomic():
                electricity_amount = int(amount)
                details = {
                    "request_id": request_id,
                    "serviceID": service_details.get("disco"),
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": service_details.get("meter_type"),
                    "amount": electricity_amount,
                    "phone": service_details.get("phone_number"),
                }
            electricity_response = top_up(details)
            return electricity_response

        elif payment_type in ["dstv", "gotv", "startimes", "showmax"]:
            plan_dict = {
                "dstv": dstv_dict,
                "gotv": gotv_dict,
                "startimes": startimes_dict,
                "showmax": showmax_dict,
            }
            with transaction.atomic():
                variation_code = plan_dict[payment_type][
                    service_details.get("plan_id")
                ][0]
                amount = plan_dict[payment_type][service_details.get("plan_id")][1]

                details = {
                    "request_id": request_id,
                    "serviceID": payment_type,
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get("phone_number"),
                }
            subscription_response = top_up(details)
            return subscription_response

        elif payment_type == "jamb":
            with transaction.atomic():
                jamb_amount = (
                    7700 if service_details.get("exam_type") == "utme-mock" else 6200
                )
                details = {
                    "request_id": request_id,
                    "serviceID": "jamb",
                    "variation_code": service_details.get("exam_type"),
                    "billersCode": service_details.get("billersCode"),
                    "phone": service_details.get("phone_number"),
                }
            registration_response = top_up(details)
            return registration_response

        elif payment_type == "waec-registration":
            with transaction.atomic():
                waec_reg_amount = 37500
                details = {
                    "request_id": request_id,
                    "serviceID": "waec-registration",
                    "variation_code": "waec-registraion",
                    "quantity": 1,
                    "phone": service_details.get("phone_number"),
                }
            registration_response = top_up(details)
            return registration_response

        elif payment_type == "waec-result":
            with transaction.atomic():
                waec_result_amount = 5350
                details = {
                    "request_id": request_id,
                    "serviceID": "waec",
                    "variation_code": "waecdirect",
                    "quantity": 1,
                    "phone": service_details.get("phone_number"),
                }
            registration_response = top_up(details)
            return registration_response


class GroupPaymentHistory(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get group payment history",
        description="List group payment history for a specific group (via group_id query param) or all groups the user belongs to. Requires JWT.",
        parameters=[
            OpenApiParameter(
                name="group_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by specific group ID",
                required=False,
            )
        ],
        responses={200: GroupPaymentSerializer(many=True)},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Response Example",
                value=[
                    {
                        "created_at": "2026-08-20T00:00:00Z",
                        "group": 1,
                        "group_name": "Family Group",
                        "id": 1,
                        "payment_type": "airtime",
                        "status": "completed",
                        "total_amount": "1000.00",
                    }
                ],
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        group_id = request.query_params.get("group_id")

        if group_id:
            is_member = GroupMember.objects.filter(
                group_id=group_id, user=request.user
            ).exists()

            if not is_member:
                return Response(
                    {"error": "You are not a member of this group"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            payments = GroupPayment.objects.filter(group_id=group_id).order_by(
                "-created_at"
            )
        else:
            user_groups = GroupMember.objects.filter(user=request.user).values_list(
                "group_id", flat=True
            )
            payments = GroupPayment.objects.filter(group_id__in=user_groups).order_by(
                "-created_at"
            )

        serializer = GroupPaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AirtimeTopUpViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase airtime",
        description="Purchase airtime for a phone number on a network. Requires a JWT bearer token; debited from the user wallet on success.",
        request=AirtimeTopUpSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Airtime Purchase",
                value={
                    "network": "mtn",
                    "phone_number": "08012345678",
                    "amount": "100",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "100",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
        tags=["Payments"],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = AirtimeTopUpSerializer(data=request.data)

            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-AIRT{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)

                with transaction.atomic():
                    amount = int(serializer.data["amount"])
                    data = {
                        "request_id": request_id,
                        "serviceID": serializer.data["network"],
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    buy_airtime_response = top_up(data)
                    if (
                        buy_airtime_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("phone_number", "")
                        network = serializer.data.get("network", "")
                        desc = get_payment_description(
                            payment_type="airtime",
                            network=network,
                            phone=phone,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="Airtime Purchase Successful",
                                message=f"₦{amount} airtime purchased for {serializer.data['phone_number']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Airtime Purchase",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(buy_airtime_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MTNDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase MTN data",
        description="Purchase an MTN data plan. Requires JWT; wallet is debited on success. `plan` must be one of the MTN data plan names; `billersCode` is the recipient phone number.",
        request=MTNDataTopUpSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "08012345678",
                    "phone_number": "08012345678",
                    "plan": "110MB Daily Plan (1 Day) - N100",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "100",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = MTNDataTopUpSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-DAT-MTN{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = mtn_dict[serializer.data["plan"]][1]
                    variation_code = mtn_dict[serializer.data["plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "mtn-data",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                    # Wallet.debit(amount)
                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("plan", "")
                        desc = get_payment_description(
                            payment_type="data",
                            network="MTN",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="MTN Data Purchase Successful",
                                message=f"₦{amount} MTN data purchased for {serializer.data['phone_number']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Data Purchase",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AirtelDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase Airtel data",
        description="Purchase an Airtel data plan. Requires JWT; wallet is debited on success.",
        request=AirtelDataTopUpSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "08012345678",
                    "phone_number": "08012345678",
                    "plan": "250MB Night Plan (12 - 5 AM) - 50 Naira  - 1Day",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "50",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = AirtelDataTopUpSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-DAT-AIR{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = airtel_dict[serializer.data["plan"]][1]
                    variation_code = airtel_dict[serializer.data["plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "airtel-data",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("plan", "")
                        desc = get_payment_description(
                            payment_type="data",
                            network="Airtel",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="Airtel Data Purchase Successful",
                                message=f"₦{amount} Airtel data purchased for {serializer.data['phone_number']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Data Purchase",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EtisalatDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase 9Mobile data",
        description="Purchase a 9mobile/etisalat data plan. Requires JWT; wallet is debited on success.",
        request=EtisalatDataTopUpSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "08012345678",
                    "phone_number": "08012345678",
                    "plan": "9mobile 100mb SME plan",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "100",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = EtisalatDataTopUpSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-DAT-ETI{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = etisalat_dict[serializer.data["plan"]][1]
                    variation_code = etisalat_dict[serializer.data["plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "etisalat-data",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("plan", "")
                        desc = get_payment_description(
                            payment_type="data",
                            network="9Mobile",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="9Mobile Data Purchase Successful",
                                message=f"₦{amount} 9Mobile data purchased for {serializer.data['phone_number']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Data Purchase",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GloDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase Glo data",
        description="Purchase a GLO data plan. Requires JWT; wallet is debited on success.",
        request=GloDataTopUpSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "08012345678",
                    "phone_number": "08012345678",
                    "plan": "120MB + 5MB Night - N100 - 1 Day",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "100",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = GloDataTopUpSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-DAT-GLO{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = glo_dict[serializer.data["plan"]][1]
                    variation_code = glo_dict[serializer.data["plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "glo-data",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }
                    # Wallet.debit(amount)
                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("plan", "")
                        desc = get_payment_description(
                            payment_type="data",
                            network="Glo",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="Glo Data Purchase Successful",
                                message=f"₦{amount} Glo data purchased for {serializer.data['phone_number']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Data Purchase",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)
        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DSTVPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Pay for DSTV subscription",
        description="Pay a DStv subscription. Requires JWT; wallet debited on success. `subscription_type` is change or renew; `billersCode` is the smartcard number.",
        request=DSTVPaymentSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "1234567890",
                    "dstv_plan": "DStv Padi N4,400",
                    "phone_number": "08012345678",
                    "subscription_type": "renew",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "4400",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = DSTVPaymentSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-TV-DS{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = dstv_dict[serializer.data["dstv_plan"]][1]
                    variation_code = dstv_dict[serializer.data["dstv_plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "dstv",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }

                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("phone_number", "")
                        plan = serializer.data.get("showmax_plan", "")
                        desc = get_payment_description(
                            payment_type="showmax",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="DSTV Subscription Successful",
                                message=f"DSTV subscription purchased for {serializer.data['billersCode']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - DSTV Subscription",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GOTVPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Pay for GOTV subscription",
        description="Pay a GOtv subscription. Requires JWT; wallet debited on success.",
        request=GOTVPaymentSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "1234567890",
                    "gotv_plan": "GOtv Max N8,500",
                    "phone_number": "08012345678",
                    "subscription_type": "renew",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "8500",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = GOTVPaymentSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-TV-GO{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = gotv_dict[serializer.data["gotv_plan"]][1]
                    variation_code = gotv_dict[serializer.data["gotv_plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "gotv",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }

                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("gotv_plan", "")
                        desc = get_payment_description(
                            payment_type="gotv",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="GOTV Subscription Successful",
                                message=f"GOTV subscription purchased for {serializer.data['billersCode']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - GOTV Subscription",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StartimesPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Pay for Startimes subscription",
        description="Pay a Startimes subscription. Requires JWT; wallet debited on success.",
        request=StartimesPaymentSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billersCode": "1234567890",
                    "phone_number": "08012345678",
                    "startimes_plan": "Nova (Dish) - 2100 Naira - 1 Month",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "2100",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = StartimesPaymentSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-TV-STA{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = startimes_dict[serializer.data["startimes_plan"]][1]
                    variation_code = startimes_dict[serializer.data["startimes_plan"]][
                        0
                    ]
                    data = {
                        "request_id": request_id,
                        "serviceID": "startimes",
                        "billersCode": serializer.data["billersCode"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }

                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("startimes_plan", "")
                        desc = get_payment_description(
                            payment_type="startimes",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="Startimes Subscription Successful",
                                message=f"Startimes subscription purchased for {serializer.data['billersCode']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Startimes Subscription",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ShowMaxPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Pay for ShowMax subscription",
        description="Pay a ShowMax subscription. Requires JWT; wallet debited on success.",
        request=ShowMaxPaymentSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "phone_number": "08012345678",
                    "showmax_plan": "Full - N8,400 - 3 Months",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "8400",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = ShowMaxPaymentSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-TV-SM{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = showmax_dict[serializer.data["showmax_plan"]][1]
                    variation_code = showmax_dict[serializer.data["showmax_plan"]][0]
                    data = {
                        "request_id": request_id,
                        "serviceID": "showmax",
                        "billersCode": serializer.data["phone_number"],
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": serializer.data["phone_number"],
                    }

                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    subscription_response = top_up(data)
                    if (
                        subscription_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        phone = serializer.data.get("billersCode", "")
                        plan = serializer.data.get("startimes_plan", "")
                        desc = get_payment_description(
                            payment_type="startimes",
                            phone=phone,
                            plan=plan,
                            amount=amount,
                        )
                        user_wallet.debit(
                            amount=amount,
                            description=desc["full"],
                            reference=request_id,
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="GOTV Subscription Successful",
                                message=f"GOTV subscription purchased for {serializer.data['billersCode']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - GOTV Subscription",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(subscription_response)
        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ElectricityPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Pay electricity bill",
        description="Pay an electricity bill for a disco (biller). Requires JWT; wallet debited on success. `biller_name` must be one of the supported disco names; `meter_type` is prepaid or postpaid.",
        request=ElectricityPaymentSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "amount": 5000,
                    "billerCode": "1234567890",
                    "biller_name": "ikeja-electric",
                    "meter_type": "prepaid",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "5000",
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        try:
            if not transaction_pin:
                return Response(
                    {"error": "Transaction PIN is required", "success": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.pin_is_set:
                return Response(
                    {
                        "error": "Please set your transaction PIN first",
                        "success": False,
                    },
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

            serializer = ElectricityPaymentSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = f'BS-LIB{generate_reference_id()}'
                serializer.save(request_id=request_id, user=request.user)
                with transaction.atomic():
                    amount = int(serializer.data["amount"])
                    data = {
                        "request_id": request_id,
                        "serviceID": serializer.data.get("biller_name"),
                        "billersCode": serializer.data["billerCode"],
                        "variation_code": serializer.data["meter_type"],
                        "amount": amount,
                        "phone": request.user.phone,
                    }
                    user_wallet = request.user.wallet

                    if user_wallet.balance < amount:
                        return Response(
                            {"error": "Insufficient Funds", "success": False},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    electricity_response = top_up(data)

                    if (
                        electricity_response.get("response_description")
                        == "TRANSACTION SUCCESSFUL"
                    ):
                        user_wallet.debit(
                            amount=amount,
                            reference=request_id,
                            description=f"Electricity - {serializer.data['biller_name'].capitalize()} {electricity_response.get('purchased_code')}",
                        )

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id,
                            )

                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status="pending",
                                    first_transaction_completed=False,
                                )
                                referral.first_transaction_completed = True
                                referral.save()

                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass

                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")

                        # Send notification
                        try:
                            send_notification(
                                user=request.user,
                                title="Electricity Payment Successful",
                                message=f"₦{amount} electricity units purchased for {serializer.data['billersCode']}",
                                notification_type="payment_success",
                                email_subject="BlueSea - Electricity Payment",
                            )
                        except Exception as e:
                            logger.error(f"Error sending notification: {str(e)}")

                    return Response(electricity_response)

        except Exception as e:
            return Response(
                {"success": False, "error": f"Payment failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WAECRegitrationViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="WAEC registration",
        description="Register for WAEC (WASSCE PIN for Private Candidates). Requires JWT; wallet debited at N37,500.",
        request=WAECRegitrationSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={"phone_number": "08012345678"},
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
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
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = WAECRegitrationSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = f'BS-WAC-{generate_reference_id()}'
            serializer.save(request_id=request_id, user=request.user)
            with transaction.atomic():
                amount = 37500
                data = {
                    "request_id": request_id,
                    "serviceID": "waec-registration",
                    "variation_code": "waec-registraion",
                    "quantity": 1,
                    "phone": serializer.data["phone_number"],
                }

                user_wallet = request.user.wallet

                if user_wallet.balance < amount:
                    return Response(
                        {"error": "Insufficient Funds", "success": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                registration_response = top_up(data)
                if (
                    registration_response.get("response_description")
                    == "TRANSACTION SUCCESSFUL"
                ):
                    desc = get_payment_description(
                        payment_type="waec-registration",
                        amount=amount,
                    )
                    user_wallet.debit(
                        amount=amount,
                        description=f"{desc['full']} {registration_response.get('purchased_code')}",
                        reference=request_id,
                    )

                    # Award bonus points
                    try:
                        award_vtu_purchase_points(
                            user=request.user,
                            purchase_amount=amount,
                            reference=request_id,
                        )

                        # Check for referral bonus (first transaction)
                        try:
                            referral = Referral.objects.get(
                                referred_user=request.user,
                                status="pending",
                                first_transaction_completed=False,
                            )
                            referral.first_transaction_completed = True
                            referral.save()

                            award_referral_bonus(referral.referrer, request.user)
                        except Referral.DoesNotExist:
                            pass

                    except Exception as e:
                        logger.error(f"Error awarding bonus points: {str(e)}")

                    # Send notification
                    try:
                        send_notification(
                            user=request.user,
                            title="WAEC Registration Successful",
                            message=f"WAEC registration completed for {serializer.data['phone_number']}",
                            notification_type="payment_success",
                            email_subject="BlueSea - WAEC Registration",
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification: {str(e)}")

                return Response(registration_response)


class WAECResultCheckerViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase WAEC result checker",
        description="Purchase a WAEC result checker. Requires JWT; wallet debited at N5,350.",
        request=WAECResultCheckerSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={"phone_number": "08012345678"},
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
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
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = WAECResultCheckerSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            request_id = f'BS-EPN-{generate_reference_id()}'
            serializer.save(request_id=request_id, user=request.user)
            with transaction.atomic():
                amount = 5350
                data = {
                    "request_id": request_id,
                    "serviceID": "waec",
                    "variation_code": "waecdirect",
                    "quantity": 1,
                    "phone": serializer.data["phone_number"],
                }

                user_wallet = request.user.wallet

                if user_wallet.balance < amount:
                    return Response(
                        {"error": "Insufficient Funds", "success": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                registration_response = top_up(data)
                if (
                    registration_response.get("response_description")
                    == "TRANSACTION SUCCESSFUL"
                ):
                    desc = get_payment_description(
                        payment_type="waec-registration",
                        amount=amount,
                    )
                    user_wallet.debit(
                        amount=amount,
                        description=f"{desc['full']} {registration_response.get('purchased_code')}",
                        reference=request_id,
                    )

                    # Award bonus points
                    try:
                        award_vtu_purchase_points(
                            user=request.user,
                            purchase_amount=amount,
                            reference=request_id,
                        )

                        # Check for referral bonus (first transaction)
                        try:
                            referral = Referral.objects.get(
                                referred_user=request.user,
                                status="pending",
                                first_transaction_completed=False,
                            )
                            referral.first_transaction_completed = True
                            referral.save()

                            award_referral_bonus(referral.referrer, request.user)
                        except Referral.DoesNotExist:
                            pass

                    except Exception as e:
                        logger.error(f"Error awarding bonus points: {str(e)}")

                    # Send notification
                    try:
                        send_notification(
                            user=request.user,
                            title="WAEC Result Purchase Successful",
                            message=f"WAEC result checker PIN purchased for {serializer.data['phone_number']}",
                            notification_type="payment_success",
                            email_subject="BlueSea - WAEC Result",
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification: {str(e)}")

                return Response(registration_response)


class JAMBRegistrationViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="JAMB registration",
        description="Register for JAMB (UTME). Requires JWT; wallet debited on success. `exam_type` is utme-mock or utme-no-mock.",
        request=JAMBRegistrationSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "billerCode": "1234567890",
                    "exam_type": "utme-no-mock",
                    "phone_number": "08012345678",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "message": "Transaction successful",
                    "request_id": "20260820ABCD1234",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
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
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = JAMBRegistrationSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            request_id = f'BS-JMB-{generate_reference_id()}'
            serializer.save(request_id=request_id, user=request.user)

            with transaction.atomic():
                amount = 7700 if serializer.data["exam_type"] == "utme-mock" else 6200
                data = {
                    "request_id": request_id,
                    "serviceID": "jamb",
                    "variation_code": serializer.data["exam_type"],
                    "billersCode": serializer.data["billerCode"],
                    "phone": serializer.data["phone_number"],
                }

                user_wallet = request.user.wallet

                if user_wallet.balance < amount:
                    return Response(
                        {"error": "Insufficient Funds", "success": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                jamb_registration_response = top_up(data)
                if (
                    jamb_registration_response.get("response_description")
                    == "TRANSACTION SUCCESSFUL"
                ):
                    exam_type = serializer.data.get("exam_type", "")
                    desc = get_payment_description(
                        payment_type="jamb",
                        exam_type=exam_type,
                        amount=amount,
                    )
                    user_wallet.debit(
                        amount=amount,
                        description=f"{desc['full']} {jamb_registration_response.get('purchased_code')}",
                        reference=request_id,
                    )

                    # Award bonus points
                    try:
                        award_vtu_purchase_points(
                            user=request.user,
                            purchase_amount=amount,
                            reference=request_id,
                        )

                        # Check for referral bonus (first transaction)
                        try:
                            referral = Referral.objects.get(
                                referred_user=request.user,
                                status="pending",
                                first_transaction_completed=False,
                            )
                            referral.first_transaction_completed = True
                            referral.save()

                            award_referral_bonus(referral.referrer, request.user)
                        except Referral.DoesNotExist:
                            pass

                    except Exception as e:
                        logger.error(f"Error awarding bonus points: {str(e)}")

                    # Send notification
                    try:
                        send_notification(
                            user=request.user,
                            title="JAMB Registration Successful",
                            message=f"JAMB registration completed for {serializer.data['phone_number']}",
                            notification_type="payment_success",
                            email_subject="BlueSea - JAMB Registration",
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification: {str(e)}")

                return Response(jamb_registration_response)


class ElectricityPaymentCustomerViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Verify electricity customer",
        description="Verify an electricity meter/customer for a disco before payment. Requires JWT.",
        request=ElectricityPaymentCustomerSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "biller": "ikeja-electric",
                    "meter_number": "1234567890",
                    "meter_type": "prepaid",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "data": {"address": "123 Allen Ave, Ikeja", "name": "JOHN DOE"},
                    "message": "Customer verified",
                    "state": True,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        try:
            serializer = ElectricityPaymentCustomerSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                serializer.save(user=request.user)

                data = {
                    "billersCode": int(serializer.data["meter_number"]),
                    "serviceID": serializer.data["biller"],
                    "type": serializer.data["meter_type"],
                }

                response = get_customer(data)
                if response["code"] == "000":
                    return Response({"success": True, "response": response["content"]})
                else:
                    return Response(
                        {"success": False, "error": "Network Error"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"success": False, "error": "Invalid User Input"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {"success": False, "error": f"Request failed: {str(e)}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InternalTransferView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Transfer funds internally",
        description="Transfer wallet funds to another BlueSea user by email. Requires JWT and transaction PIN.",
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Internal Transfer",
                value={
                    "transaction_pin": "1234",
                    "email": "recipient@example.com",
                    "amount": "5000",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "amount": "5000",
                    "message": "Transfer successful",
                    "recipient": "recipient@example.com",
                    "state": True,
                },
                response_only=True,
            ),
        ],
        tags=["Payments"],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")
        recipient_email = request.data.get("email")
        amount = request.data.get("amount")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
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
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not recipient_email:
            return Response(
                {"error": "Recipient email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not amount or Decimal(str(amount)) <= 0:
            return Response(
                {"error": "Valid amount is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = Decimal(str(amount))

        # Get recipient user
        try:
            recipient = User.objects.get(email=recipient_email)
        except User.DoesNotExist:
            return Response(
                {"error": "Recipient not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if recipient == request.user:
            return Response(
                {"error": "Cannot transfer to yourself"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sender_wallet = request.user.wallet

        if sender_wallet.balance < amount:
            return Response(
                {"error": "Insufficient funds"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sender_reference = f'BS-INT-{generate_reference_id()}'
        recipient_reference =f'BS-INT-{generate_reference_id()}'

        try:
            with transaction.atomic():
                # Debit sender
                sender_wallet.debit(
                    amount=amount,
                    description=f"Internal transfer to {recipient.email}",
                    reference=sender_reference,
                )

                # Credit recipient
                recipient_wallet = recipient.wallet
                recipient_wallet.credit(
                    amount=amount,
                    description=f"Internal transfer from {request.user.email}",
                    reference=recipient_reference,
                )

                # Send notification to sender
                try:
                    send_notification(
                        user=request.user,
                        title="Transfer Successful",
                        message=f"₦{amount} transferred to {recipient.email}",
                        notification_type="payment_success",
                        email_subject="BlueSea - Transfer Successful",
                    )
                except Exception as e:
                    logger.error(f"Error sending notification: {str(e)}")

                # Send notification to recipient
                try:
                    send_notification(
                        user=recipient,
                        title=" funds Received",
                        message=f"₦{amount} received from {request.user.email}",
                        notification_type="payment_success",
                        email_subject="BlueSea - Funds Received",
                    )
                except Exception as e:
                    logger.error(f"Error sending notification: {str(e)}")

            return Response(
                {
                    "success": True,
                    "message": "Transfer successful",
                    "reference": sender_reference,
                    "amount": str(amount),
                    "recipient": recipient.email,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"success": False, "error": f"Transfer failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WithdrawalView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Request a withdrawal",
        description="Withdraw wallet funds to a bank account. Requires JWT and transaction PIN; validates PIN, bank details, and minimum amount (N500). Returns a withdrawal record (status pending).",
        request=WithdrawalRequestSerializer,
        responses={
            201: WithdrawalResponseSerializer,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=["Payments"],
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "account_name": "John Doe",
                    "account_number": "0123456789",
                    "amount": "5000.00",
                    "bank_code": "058",
                    "bank_name": "GTBank",
                    "transaction_pin": "1234",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Response Example",
                value={
                    "message": "Withdrawal initiated successfully",
                    "state": True,
                    "withdrawal": {
                        "account_name": "John Doe",
                        "account_number": "0123456789",
                        "amount": "5000.00",
                        "bank_code": "058",
                        "bank_name": "GTBank",
                        "completed_at": None,
                        "created_at": "2026-08-20T00:00:00Z",
                        "id": 1,
                        "payment_reference": "WD-20260820ABCD",
                        "status": "pending",
                    },
                },
                response_only=True,
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

        user_wallet = request.user.wallet
        if user_wallet.balance < amount:
            return Response(
                {"error": "Insufficient funds", "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                reference_id = f'BS-WIT-{generate_reference_id()}'
                withdrawal = Withdrawal.objects.create(
                    user=request.user,
                    account_name=account_name,
                    account_number=account_number,
                    bank_code=bank_code,
                    bank_name=bank_name,
                    amount=amount,
                    payment_reference=reference_id,
                    status="pending",
                )

                user_wallet.debit(
                    amount=amount,
                    description=f"Withdrawal to {account_name} ({account_number})",
                    reference=reference_id,
                )

                # Notify the user that the request was received
                try:
                    send_notification(
                        user=request.user,
                        title="Withdrawal Request Received",
                        message=(
                            f"₦{amount} withdrawal to {account_name} "
                            "received. It will be processed shortly."
                        ),
                        notification_type="payment",
                        email_subject="BlueSea - Withdrawal Request Received",
                    )
                except Exception as e:
                    logger.error(f"Error sending withdrawal notification: {str(e)}")

                response_serializer = WithdrawalResponseSerializer(
                    {
                        "state": True,
                        "message": "Withdrawal request submitted",
                        "withdrawal": withdrawal,
                    }
                )
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Error processing withdrawal: {str(e)}")
            return Response(
                {"success": False, "error": f"Withdrawal failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
