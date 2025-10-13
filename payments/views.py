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
    )
from notifications.utils import contribution_notification, group_payment_success, group_payment_failed
from bluesea_mobile.utils import InsufficientFundsException, VTUAPIException
    
class GroupPaymentViews(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        group_id = request.data.get('group_id')
        payment_type = request.data.get('payment_type')
        total_amount = Decimal(str(request.data.get('total_amount')))
        service_details = request.data.get('service_details')
        split_type = request.data.get('split_type', 'equal')
        custom_splits = request.data.get('custom_splits', {})

        group = get_object_or_404(Group, id=group_id)
        
        #TODO: work on check if user is admin
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
                for member, amount in member_amounts.items():
                    wallet = member.user.wallet
                    
                    if wallet.balance < amount:
                        raise InsufficientFundsException(
                            f"Insufficient funds for {member.user.get_full_name()}"
                        )
                    
                    wallet.debit(amount, reference=f'GP-{group_payment.id}-{member.user.id}')

                    # Create transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='debit',
                        amount=amount,
                        description=f'Group payment contribution - {payment_type}',
                        reference=f'GP-{group_payment.id}-{member.user.id}',
                        status='completed'
                    )

                    # Create contribution record
                    contribution = GroupPaymentContribution.objects.create(
                        group_payment=group_payment,
                        member=member,
                        amount=amount,
                        status='completed'
                    )

                    contribution_notification(
                        member=member,
                        amount=amount,
                        group_name=group.name,
                        payment_type=payment_type
                    )

                # All debits successful, now call VTU API
                vtu_response = self.vtu_api(payment_type, service_details, total_amount)
                
                if vtu_response.get('status') == 'success':
                    group_payment.status = 'completed'
                    group_payment.vtu_reference = vtu_response.get('reference')
                    group_payment.save()
                    
                    # Notify all members of success
                    for member in members:
                        group_payment_success(
                            member=member,
                            amount=total_amount,
                            group_name=group.name,
                            payment_type=payment_type,
                            vtu_reference=vtu_response.get('reference')
                        )
                    
                    return Response({
                        'message': 'Group payment completed successfully',
                        'payment_id': group_payment.id,
                        'vtu_reference': vtu_response.get('reference')
                    }, status=status.HTTP_200_OK)
                else:
                    raise VTUAPIException(vtu_response.get('message', 'VTU API failed'))

        except InsufficientFundsException as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            for member in members:
                group_payment_failed(
                    member=member,
                    amount=member_amounts.get(member, 0),
                    group_name=group.name,
                    payment_type=payment_type,
                    reason=str(e)
                )
            
            return Response(
                {'error': f'Payment failed: {str(e)}. All debits have been reversed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}. All debits have been reversed.'},
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
                        "billerCode": service_details.get('billerCode'),
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
                        "billerCode": service_details.get('billerCode'),
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
                        "billerCode": service_details.get('billerCode'),
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
                        "billerCode": service_details.get('billerCode'),
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
                    "billerCode": service_details.get('billerCode'),
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
                    "billerCode": service_details.get('billerCode'),
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
                    "billerCode" : service_details.get('billerCode'),
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
    #permission_classes = [IsAuthenticated]
    
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
                #user_wallet = request.user.wallet
                #Wallet.debit(amount, ref_id)
                buy_airtime_response = top_up(data)
                #if buy_airtime_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                    #user_wallet.debit(amount=amount, reference=request_id)
                
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

