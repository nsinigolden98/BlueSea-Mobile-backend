
from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from group_payment.models import Group, GroupMember
from wallet.models import Wallet
from .models import GroupPayment, GroupPaymentContribution
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
    ElectricityPaymentCustomerSerializer
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
from .vtuafrica import (
    top_up2,
    )
from notifications.utils import contribution_notification, group_payment_success, group_payment_failed
from bluesea_mobile.utils import InsufficientFundsException, VTUAPIException
from bonus.utils import award_daily_login_bonus, award_points, award_referral_bonus, award_vtu_purchase_points, user_points_summary, redeem_points
from bonus.models import Referral, BonusCampaign, BonusHistory, BonusPoint
import logging
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import uuid

logger = logging.getLogger(__name__)

VTU_AFRICA_APIKEY = ""

class Airtime2CashViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Convert airtime to cash",
        description="Convert airtime to wallet balance",
        request=Airtime2CashSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=['Payments']
    )
    
    def post(self, request):
        serializer = Airtime2CashSerializer(data = request.data)
        
        if serializer.is_valid(raise_exception=True):
            request_id = generate_reference_id()
            serializer.save(request_id = request_id)
            
            with transaction.atomic():
                amount = int(serializer.data['amount'])
    
                user_data = {
                             "apikey":"",
                             "serviceName":"Airtime2Cash",
                            "network":serializer.data["network"]
                                        }

                sitephone= top_up2(user_data,"merchant-verify")
                if sitephone !=  "Unavailable":
                    user_data = {
                                "apikey":"",
                                "network":serializer.data["network"],
                                "sender":"",
                                "sendernumber":serializer.data["phone_number"],
                                "amount":amount,
                                "ref": request_id,
                                "sitephone": sitephone
                    }
                    user_wallet = request.user.wallet
                    airtime2cash_response = top_up2(user_data, "airtime-cash")
                    if airtime2cash_response["code"] == 101:
                        user_wallet.credit(amount=amount, reference=request_id)
                        
class GroupPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create group payment",
        description="Initiate a group payment for services like airtime, data, electricity, etc.",
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Group Airtime Payment',
                value={
                    "group_id": 1,
                    "payment_type": "airtime",
                    "total_amount": "1000.00",
                    "service_details": {
                        "network": "mtn",
                        "phone_number": "08012345678"
                    },
                    "split_type": "equal"
                },
                request_only=True
            )
        ],
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)
        
        group_id = request.data.get('group_id')
        payment_type = request.data.get('payment_type')
        total_amount = Decimal(str(request.data.get('total_amount')))
        service_details = request.data.get('service_details')
        split_type = request.data.get('split_type', 'equal')
        custom_splits = request.data.get('custom_splits', {})


        group = get_object_or_404(Group, id=group_id)
        
        # Check if user is admin/owner
        is_admin = GroupMember.objects.filter(
            group=group,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()
        
        if not is_admin:
            return Response(
                {'error': 'Only group admins can initiate payments'},
                status=status.HTTP_403_FORBIDDEN
            )

        members = GroupMember.objects.filter(group=group).select_related('user', 'user__wallet')

        if members.count() == 0:
            return Response(
                {'error': 'No active members in group'},
                status=status.HTTP_400_BAD_REQUEST
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
                    status='processing'
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
                    unique_reference = f'GP-{group_payment.id}-{member.user.id}-{uuid.uuid4().hex[:8]}'
                    
                    # Debit wallet with unique reference
                    wallet.debit(
                        amount=amount, 
                        description=f'Group payment contribution - {payment_type}',
                        reference=unique_reference
                    )

                    # Create contribution record
                    GroupPaymentContribution.objects.create(
                        group_payment=group_payment,
                        member=member,
                        amount=amount,
                        status='completed'
                    )

                    # Send notification
                    try:
                        contribution_notification(
                            member=member,
                            amount=amount,
                            group_name=group.name,
                            payment_type=payment_type
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notification to {member.user.email}: {str(e)}")

                # All debits successful, now call VTU API
                vtu_response = self.vtu_api(payment_type, service_details, total_amount)
                
                if vtu_response.get('response_description') == 'TRANSACTION SUCCESSFUL':
                    group_payment.status = 'completed'
                    group_payment.vtu_reference = vtu_response.get('requestId', vtu_response.get('reference'))
                    group_payment.save()
                    
                    # Notify all members of success
                    for member in members:
                        try:
                            group_payment_success(
                                member=member,
                                amount=member_amounts.get(member),
                                group_name=group.name,
                                payment_type=payment_type,
                                vtu_reference=vtu_response.get('requestId')
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send success notification: {str(e)}")
                    
                    return Response({
                        'success': True,
                        'message': 'Group payment completed successfully',
                        'payment_id': group_payment.id,
                        'vtu_reference': group_payment.vtu_reference,
                        'total_amount': str(total_amount),
                        'member_contributions': {
                            member.user.email: str(member_amounts.get(member))
                            for member in members
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    # VTU API failed
                    group_payment.status = 'failed'
                    group_payment.save()
                    
                    # Reverse all debits by crediting back
                    for member in members:
                        amount = member_amounts.get(member)
                        wallet = member.user.wallet
                        reversal_reference = f'REV-{group_payment.id}-{member.user.id}-{uuid.uuid4().hex[:8]}'
                        
                        wallet.credit(
                            amount=amount,
                            description=f'Reversal - Group payment failed',
                            reference=reversal_reference
                        )
                    
                    return Response({
                        'success': False,
                        'error': f'VTU service failed: {vtu_response.get("response_description", "Unknown error")}. All debits have been reversed.',
                        'payment_id': group_payment.id
                    }, status=status.HTTP_400_BAD_REQUEST)

        except InsufficientFundsException as e:
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
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
                        reason=str(e)
                    )
                except Exception as notif_error:
                    logger.warning(f"Failed to send failure notification: {str(notif_error)}")
            
            return Response(
                {
                    'success': False,
                    'error': f'Payment failed: {str(e)}. All debits have been reversed.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def _calculate_splits(self, members, total_amount, split_type, custom_splits):
        member_amounts = {}
        
        if split_type == 'equal':
            amount_per_member = total_amount / members.count()
            for member in members:
                member_amounts[member] = amount_per_member
        
        elif split_type == 'percentage':
            for member in members:
                percentage = Decimal(str(custom_splits.get(str(member.user.id), 0)))
                member_amounts[member] = (total_amount * percentage) / 100
        
        return member_amounts


    def vtu_api(self, payment_type, service_details, amount):
        request_id = generate_reference_id()
                
        if payment_type == 'airtime':
            with transaction.atomic():
                airtime_amount = int(amount)
                details = {
                    "request_id": request_id,
                    "serviceID": service_details.get('network'),
                    "amount": airtime_amount,
                    "phone": service_details.get('phone_number')
                }
            subscription_response = top_up(details)
            return subscription_response
        
        elif payment_type == 'data':
            if service_details.get('network') == 'mtn':
                with transaction.atomic():
                    variation_code = mtn_dict[service_details.get('plan_id')][0]
                    amount = mtn_dict[service_details.get('plan_id')][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "mtn-data",
                        "billersCode": service_details.get('billersCode'),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get('phone_number'),
                    }
                subscription_response = top_up(details)
                return subscription_response
            elif service_details.get('network') == 'airtel':
                with transaction.atomic():
                    variation_code = airtel_dict[service_details.get('plan_id')][0]
                    amount = airtel_dict[service_details.get('plan_id')][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "airtel-data",
                        "billersCode": service_details.get('billersCode'),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get('phone_number'),
                    }
                subscription_response = top_up(details)
                return subscription_response

            elif service_details.get('network') == 'glo':
                with transaction.atomic():
                    variation_code = glo_dict[service_details.get('plan_id')][0]
                    amount = glo_dict[service_details.get('plan_id')][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "glo-data",
                        "billersCode": service_details.get('billersCode'),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get('phone_number'),
                    }
                subscription_response = top_up(details)
                return subscription_response
            
            elif service_details.get('network') == 'etisalat':
                with transaction.atomic():
                    variation_code = etisalat_dict[service_details.get('plan_id')][0]
                    amount = etisalat_dict[service_details.get('plan_id')][1]

                    details = {
                        "request_id": request_id,
                        "serviceID": "etisalat-data",
                        "billersCode": service_details.get('billersCode'),
                        "variation_code": variation_code,
                        "amount": amount,
                        "phone": service_details.get('phone_number'),
                    }


        elif payment_type == 'electricity':
            # return vtu_service.purchase_electricity(
            #     meter_number=service_details.get('meter_number'),
            #     amount=amount,
            #     disco=service_details.get('disco')
            # )

            with transaction.atomic():
                electricity_amount = int(amount)
                details = {
                    "request_id": request_id,
                    "serviceID": service_details.get('disco'),
                    "billersCode": service_details.get('billersCode'),
                    "variation_code": service_details.get('meter_type'),
                    "amount": electricity_amount,
                    "phone": service_details.get('phone_number')
                }
            electricity_response = top_up(details)
            return electricity_response
        
        elif payment_type in ['dstv', 'gotv', 'startimes', 'showmax']:
            plan_dict = {
                'dstv': dstv_dict,
                'gotv': gotv_dict,
                'startimes': startimes_dict,
                'showmax': showmax_dict
            }
            with transaction.atomic():
                variation_code = plan_dict[payment_type][service_details.get('plan_id')][0]
                amount = plan_dict[payment_type][service_details.get('plan_id')][1]

                details = {
                    "request_id": request_id,
                    "serviceID": payment_type,
                    "billersCode": service_details.get('billersCode'),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get('phone_number'),
                }
            subscription_response = top_up(details)
            return subscription_response

        elif payment_type == 'jamb':
            with transaction.atomic():
                jamb_amount = 7700 if service_details.get('exam_type') == 'utme-mock' else 6200
                details = {
                    "request_id": request_id,
                    "serviceID": "jamb",
                    "variation_code": service_details.get('exam_type'),
                    "billersCode" : service_details.get('billersCode'),
                    "phone": service_details.get('phone_number')
                }
            registration_response = top_up(details)
            return registration_response
        
        elif payment_type == 'waec-registration':
            with transaction.atomic():
                waec_reg_amount = 14500
                details = {
                    "request_id": request_id,
                    "serviceID": "waec-registration",
                    "variation_code": "waec-registration",
                    "quantity" : 1,
                    "phone": service_details.get('phone_number')
                }
            registration_response = top_up(details)
            return registration_response
        
        elif payment_type == 'waec-result':
            with transaction.atomic():
                waec_result_amount = 950
                details = {
                    "request_id": request_id,
                    "serviceID": "waec",
                    "variation_code": "waecdirect",
                    "quantity" : 1,
                    "phone": service_details.get('phone_number')
                }
            registration_response = top_up(details)
            return registration_response

class GroupPaymentHistory(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get group payment history",
        description="Retrieve payment history for a specific group or all user's groups",
        parameters=[
            OpenApiParameter(
                name='group_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter by specific group ID',
                required=False
            )
        ],
        responses={200: GroupPaymentSerializer(many=True)},
        tags=['Payments']
    )
    def get(self, request):
        group_id = request.query_params.get('group_id')
        
        if group_id:
            is_member = GroupMember.objects.filter(
                group_id=group_id,
                user=request.user
            ).exists()
            
            if not is_member:
                return Response(
                    {'error': 'You are not a member of this group'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            payments = GroupPayment.objects.filter(group_id=group_id).order_by('-created_at')
        else:
            user_groups = GroupMember.objects.filter(user=request.user).values_list('group_id', flat=True)
            payments = GroupPayment.objects.filter(group_id__in=user_groups).order_by('-created_at')
        
        serializer = GroupPaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AirtimeTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Purchase airtime",
        description="Buy airtime for a phone number",
        request=AirtimeTopUpSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Airtime Purchase',
                value={
                    "network": "mtn",
                    "phone_number": "08012345678",
                    "amount": "100"
                },
                request_only=True
            )
        ],
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        try:
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', "success" :False}, status=status.HTTP_400_BAD_REQUEST)
    
            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', "success": False}, status=status.HTTP_400_BAD_REQUEST)
    
            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', "success": False}, status=status.HTTP_400_BAD_REQUEST)
            
    
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
                    
                    if user_wallet.balance < amount:
                        return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
    
                    buy_airtime_response = top_up(data)
                    if buy_airtime_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, description="Airtime Purchase", reference=request_id)
                    
                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    
                    return Response(buy_airtime_response)
                    
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class MTNDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Purchase MTN data",
        description="Buy MTN data bundle",
        request=MTNDataTopUpSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')
        
        try:
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', "success": False}, status=status.HTTP_400_BAD_REQUEST)
    
            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', "success": False}, status=status.HTTP_400_BAD_REQUEST)
    
            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', "success": False}, status=status.HTTP_400_BAD_REQUEST)
    
    
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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                        }
                    # Wallet.debit(amount) 
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                        return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
    
                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, description= "MTN Data Subscription",reference=request_id)
    
                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
                    
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                    
class AirtelDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Purchase Airtel data",
        description="Buy Airtel data bundle",
        request=AirtelDataTopUpSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        try:
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', "success": False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', "success": False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', "success": False}, status=status.HTTP_400_BAD_REQUEST)
            

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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                        }
                    # Wallet.debit(amount) 
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                            return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
                            
                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, description= "Airtel Data Subscription",reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
                
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                    
class GloDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Purchase Glo data",
        description="Buy Glo data bundle",
        request=GloDataTopUpSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')
        
        try:
            
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', "success": False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', "success": False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', "success": False}, status=status.HTTP_400_BAD_REQUEST)
            

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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                        }
                    # Wallet.debit(amount) 
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                                return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)               

                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, description= " Glo Data Subscription",reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )    
class EtisalatDataTopUpViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Purchase 9mobile data",
        description="Buy 9mobile (Etisalat) data bundle",
        request=EtisalatDataTopUpSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        try:
            
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', "success": False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', "success": False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', "success": False}, status=status.HTTP_400_BAD_REQUEST)
            

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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                        }
                    # Wallet.debit(amount) 
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                            return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
                            

                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, description= " 9mobile Data Subscription",reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
                
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )            
class DSTVPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Pay for DSTV subscription",
        description="Purchase DSTV subscription plan",
        request=DSTVPaymentSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')
        
        try:
            
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
            

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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                            "subscription_type": serializer.data["subscription_type"],
                            "quanity" : 1
                        }
                    # Wallet.debit(amount) 
                    user_wallet = request.user.wallet
                    if user_wallet.balance < amount:
                            return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
                            
                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
                
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                    
class GOTVPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Pay for GOTV subscription",
        description="Purchase GOTV subscription plan",
        request=GOTVPaymentSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')
        
        try:

            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)


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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                            "subscription_type": serializer.data["subscription_type"],
                            "quanity" : 1
                        }
                    # Wallet.debit(amount) 
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                            return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
                            

                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                    
class StartimesPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Pay for Startimes subscription",
        description="Purchase Startimes subscription plan",
        request=StartimesPaymentSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')
        
        try:

            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', 'success': False}, status=status.HTTP_400_BAD_REQUEST)


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
                            "billersCode": serializer.data["billersCode"],
                            "variation_code": variation_code,
                            "amount": amount,
                            "phone": serializer.data["phone_number"],
                        }
                    
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                                return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
                                

                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
                
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                
class ShowMaxPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Pay for ShowMax subscription",
        description="Purchase ShowMax subscription plan",
        request=ShowMaxPaymentSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')
        
        try:

            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', 'success': False}, status=status.HTTP_400_BAD_REQUEST)


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
                            "billersCode": serializer.data["phone_number"],
                            "variation_code": variation_code,
                            "amount": amount,
                        }
                    
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                            return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
                            

                    subscription_response = top_up(data)
                    if subscription_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id)

                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(subscription_response)
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )       
class ElectricityPaymentViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Pay electricity bill",
        description="Purchase electricity/power units",
        request=ElectricityPaymentSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        try:
            if not transaction_pin:
                return Response({'error': 'Transaction PIN is required','success': False}, status=status.HTTP_400_BAD_REQUEST)
    
            if not request.user.pin_is_set:
                return Response({'error': 'Please set your transaction PIN first', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
    
            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({'error': 'Invalid transaction PIN', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
            
    
            serializer = ElectricityPaymentSerializer(data = request.data)
            if serializer.is_valid(raise_exception=True):
                request_id = generate_reference_id()
                serializer.save(request_id = request_id)
                with transaction.atomic():
                    amount = int(serializer.data["amount"])
                    data = {
                            "request_id": request_id,
                            "serviceID": serializer.data["biller_name"],
                            "billersCode": serializer.data["billerCode"],
                            "variation_code": serializer.data["meter_type"],
                            "amount": amount,
                            "phone": request.user.phone
                        } 
                    user_wallet = request.user.wallet
                    
                    if user_wallet.balance < amount:
                        return Response({'error': 'Insufficient Funds', 'success': False}, status=status.HTTP_400_BAD_REQUEST)
    
                    electricity_response = top_up(data)

                    if electricity_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                        user_wallet.debit(amount=amount, reference=request_id, description=f"Electricity - {serializer.data['biller_name'].capitalize()}")
                        
                    
                        # Award bonus points
                        try:
                            award_vtu_purchase_points(
                                user=request.user,
                                purchase_amount=amount,
                                reference=request_id
                            )
                            
                            # Check for referral bonus (first transaction)
                            try:
                                referral = Referral.objects.get(
                                    referred_user=request.user,
                                    status='pending',
                                    first_transaction_completed=False
                                )
                                referral.first_transaction_completed = True
                                referral.save()
                                
                                award_referral_bonus(referral.referrer, request.user)
                            except Referral.DoesNotExist:
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error awarding bonus points: {str(e)}")
                    return Response(electricity_response)

        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Payment failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class WAECRegitrationViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="WAEC registration",
        description="Register for WAEC examination",
        request=WAECRegitrationSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)


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
                
                user_wallet = request.user.wallet 
                registration_response = top_up(data)
                if registration_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)

                    # Award bonus points
                    try:
                        award_vtu_purchase_points(
                            user=request.user,
                            purchase_amount=amount,
                            reference=request_id
                        )
                        
                        # Check for referral bonus (first transaction)
                        try:
                            referral = Referral.objects.get(
                                referred_user=request.user,
                                status='pending',
                                first_transaction_completed=False
                            )
                            referral.first_transaction_completed = True
                            referral.save()
                            
                            award_referral_bonus(referral.referrer, request.user)
                        except Referral.DoesNotExist:
                            pass
                            
                    except Exception as e:
                        logger.error(f"Error awarding bonus points: {str(e)}")
                return Response(registration_response)
                
class WAECResultCheckerViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Purchase WAEC result checker",
        description="Buy WAEC result checker PIN",
        request=WAECResultCheckerSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)
        

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

                user_wallet = request.user.wallet

                registration_response = top_up(data)
                if registration_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)

                    # Award bonus points
                    try:
                        award_vtu_purchase_points(
                            user=request.user,
                            purchase_amount=amount,
                            reference=request_id
                        )
                        
                        # Check for referral bonus (first transaction)
                        try:
                            referral = Referral.objects.get(
                                referred_user=request.user,
                                status='pending',
                                first_transaction_completed=False
                            )
                            referral.first_transaction_completed = True
                            referral.save()
                            
                            award_referral_bonus(referral.referrer, request.user)
                        except Referral.DoesNotExist:
                            pass
                            
                    except Exception as e:
                        logger.error(f"Error awarding bonus points: {str(e)}")
                return Response(registration_response)
                
class JAMBRegistrationViews(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="JAMB registration",
        description="Register for JAMB examination",
        request=JAMBRegistrationSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)


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
                    "billersCode" : serializer.data["billersCode"],
                    "phone": serializer.data["phone_number"]
                }
                
                user_wallet = request.user.wallet 
                jamb_registration_response = top_up(data)
                if jamb_registration_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    user_wallet.debit(amount=amount, reference=request_id)

                    # Award bonus points
                    try:
                        award_vtu_purchase_points(
                            user=request.user,
                            purchase_amount=amount,
                            reference=request_id
                        )
                        
                        # Check for referral bonus (first transaction)
                        try:
                            referral = Referral.objects.get(
                                referred_user=request.user,
                                status='pending',
                                first_transaction_completed=False
                            )
                            referral.first_transaction_completed = True
                            referral.save()
                            
                            award_referral_bonus(referral.referrer, request.user)
                        except Referral.DoesNotExist:
                            pass
                            
                    except Exception as e:
                        logger.error(f"Error awarding bonus points: {str(e)}")
                return Response                 (jamb_registration_response)


class ElectricityPaymentCustomerViews(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self,request):
        try:
            serializer =  ElectricityPaymentCustomerSerializer(data= request.data)
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                
                data = {
                    'billersCode': serializer.data['meter_number'],
                    'serviceID' : serializer.data['biller'],
                    'type': serializer.data['meter_type'], 
                }
                
                response = get_customer(data)
                if response['code'] == '000':
                    return Response({
                        'success': True,
                        'response': response["content"]
                    })
                else:
                    return Response({
                        'success': False,
                        'error': "Network Error"
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                    return Response({
                        'success': False,
                        'error': "Invalid User Input"
                    }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                    'success': False,
                    'error': f'Request failed: {str(e)}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )