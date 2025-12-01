from celery import shared_task
from django.db import transaction as db_transaction
from django.core.cache import cache
from decimal import Decimal
import logging
import uuid
from .models import GroupPayment, GroupPaymentContribution
from .vtpass import top_up, generate_reference_id
from .vtpass import dstv_dict, gotv_dict, startimes_dict, showmax_dict
from .vtpass import mtn_dict, airtel_dict, glo_dict, etisalat_dict
from wallet.models import Wallet
from transactions.models import WalletTransaction
from notifications.utils import send_notification, contribution_notification, group_payment_success, group_payment_failed
from bonus.utils import award_vtu_purchase_points, award_referral_bonus
from bonus.models import Referral
from accounts.models import Profile


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_vtu_purchase(self, user_id, service_type, service_data, amount, reference, description="VTU Purchase"):
    
    try:
        user = Profile.objects.get(id=user_id)
        wallet = user.wallet
        
        # Call VTU API
        vtu_response = top_up(service_data)
        
        if vtu_response.get("response_description") == "TRANSACTION SUCCESSFUL":
            # Debit wallet
            with db_transaction.atomic():
                wallet.debit(
                    amount=amount,
                    description=description,
                    reference=reference
                )
                
                # Clear wallet balance cache
                cache.delete(f'wallet_balance_{user_id}')
            
            # Award bonus points asynchronously
            try:
                award_vtu_purchase_points(
                    user=user,
                    purchase_amount=amount,
                    reference=reference
                )
                
                # Check for first transaction referral bonus
                try:
                    referral = Referral.objects.get(
                        referred_user=user,
                        status='pending',
                        first_transaction_completed=False
                    )
                    referral.first_transaction_completed = True
                    referral.save()
                    award_referral_bonus(referral.referrer, user)
                except Referral.DoesNotExist:
                    pass
                    
            except Exception as e:
                logger.error(f"Error awarding bonus points: {str(e)}")
            
            # Send success notification
            send_notification(
                user=user,
                title=f"{service_type.upper()} Purchase Successful",
                message=f"Your {service_type} purchase of ₦{amount} was successful.",
                notification_type='success'
            )
            
            logger.info(f"VTU purchase successful for user {user_id}: {reference}")
            return {
                'success': True,
                'response': vtu_response,
                'reference': reference
            }
        else:
            # VTU failed
            logger.error(f"VTU purchase failed: {vtu_response}")
            send_notification(
                user=user,
                title=f"{service_type.upper()} Purchase Failed",
                message=f"Your {service_type} purchase failed. Please try again.",
                notification_type='error'
            )
            return {
                'success': False,
                'response': vtu_response
            }
            
    except Exception as e:
        logger.error(f"Error processing VTU purchase: {str(e)}", exc_info=True)
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def process_group_payment(self, group_payment_id):

    try:
        group_payment = GroupPayment.objects.select_related('group', 'initiated_by').get(id=group_payment_id)
        
        # Call VTU API
        payment_type = group_payment.payment_type
        service_details = group_payment.service_details
        total_amount = group_payment.total_amount
        
        # Generate VTU request
        request_id = generate_reference_id()
        vtu_data = build_vtu_data(payment_type, service_details, total_amount, request_id)
        
        vtu_response = top_up(vtu_data)
        
        if vtu_response.get('response_description') == 'TRANSACTION SUCCESSFUL':
            with db_transaction.atomic():
                group_payment.status = 'completed'
                group_payment.vtu_reference = vtu_response.get('requestId', vtu_response.get('reference'))
                group_payment.save()
                
                # Clear cache for all members
                contributions = GroupPaymentContribution.objects.filter(
                    group_payment=group_payment
                ).select_related('member__user')
                
                for contribution in contributions:
                    cache.delete(f'wallet_balance_{contribution.member.user.id}')
                    
                    # Notify success
                    try:
                        group_payment_success(
                            member=contribution.member,
                            amount=contribution.amount,
                            group_name=group_payment.group.name,
                            payment_type=payment_type,
                            vtu_reference=group_payment.vtu_reference
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send success notification: {str(e)}")
            
            logger.info(f"Group payment {group_payment_id} completed successfully")
            return {
                'success': True,
                'payment_id': group_payment_id,
                'vtu_reference': group_payment.vtu_reference
            }
        else:
            # VTU failed - reverse all debits
            with db_transaction.atomic():
                group_payment.status = 'failed'
                group_payment.save()
                
                contributions = GroupPaymentContribution.objects.filter(
                    group_payment=group_payment
                ).select_related('member__user__wallet')
                
                for contribution in contributions:
                    # Reverse debit
                    wallet = contribution.member.user.wallet
                    reversal_reference = f'REV-{group_payment.id}-{contribution.member.user.id}-{uuid.uuid4().hex[:8]}'
                    
                    wallet.credit(
                        amount=contribution.amount,
                        description=f'Reversal - Group payment failed',
                        reference=reversal_reference
                    )
                    
                    # Clear cache
                    cache.delete(f'wallet_balance_{contribution.member.user.id}')
                    
                    # Notify failure
                    try:
                        group_payment_failed(
                            member=contribution.member,
                            amount=contribution.amount,
                            group_name=group_payment.group.name,
                            payment_type=payment_type,
                            reason=vtu_response.get('response_description', 'Unknown error')
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send failure notification: {str(e)}")
            
            logger.error(f"Group payment {group_payment_id} failed: {vtu_response}")
            return {
                'success': False,
                'error': vtu_response.get('response_description', 'Unknown error')
            }
            
    except Exception as e:
        logger.error(f"Error processing group payment {group_payment_id}: {str(e)}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': str(e)
        }


def build_vtu_data(payment_type, service_details, amount, request_id):
    
    if payment_type == 'airtime':
        return {
            "request_id": request_id,
            "serviceID": service_details.get('network'),
            "amount": int(amount),
            "phone": service_details.get('phone_number')
        }
    
    elif payment_type == 'data':
        network = service_details.get('network')
        plan_dicts = {
            'mtn': mtn_dict,
            'airtel': airtel_dict,
            'glo': glo_dict,
            'etisalat': etisalat_dict
        }
        
        plan_dict = plan_dicts.get(network, {})
        plan_info = plan_dict.get(service_details.get('plan_id'), [None, amount])
        
        return {
            "request_id": request_id,
            "serviceID": f"{network}-data",
            "billersCode": service_details.get('billersCode'),
            "variation_code": plan_info[0],
            "amount": int(plan_info[1]),
            "phone": service_details.get('phone_number'),
        }
    
    elif payment_type == 'electricity':
        return {
            "request_id": request_id,
            "serviceID": service_details.get('disco'),
            "billersCode": service_details.get('billersCode'),
            "variation_code": service_details.get('meter_type'),
            "amount": int(amount),
            "phone": service_details.get('phone_number')
        }
    
    elif payment_type in ['dstv', 'gotv', 'startimes', 'showmax']:
        plan_dict = {
            'dstv': dstv_dict,
            'gotv': gotv_dict,
            'startimes': startimes_dict,
            'showmax': showmax_dict
        }[payment_type]
        
        plan_info = plan_dict[service_details.get('plan_id')]
        
        return {
            "request_id": request_id,
            "serviceID": payment_type,
            "billersCode": service_details.get('billersCode'),
            "variation_code": plan_info[0],
            "amount": int(plan_info[1]),
            "phone": service_details.get('phone_number'),
        }
    
    elif payment_type == 'jamb':
        amount = 7700 if service_details.get('exam_type') == 'utme-mock' else 6200
        return {
            "request_id": request_id,
            "serviceID": "jamb",
            "variation_code": service_details.get('exam_type'),
            "billersCode": service_details.get('billersCode'),
            "phone": service_details.get('phone_number')
        }
    
    elif payment_type == 'waec-registration':
        return {
            "request_id": request_id,
            "serviceID": "waec-registration",
            "variation_code": "waec-registration",
            "quantity": 1,
            "phone": service_details.get('phone_number')
        }
    
    elif payment_type == 'waec-result':
        return {
            "request_id": request_id,
            "serviceID": "waec",
            "variation_code": "waecdirect",
            "quantity": 1,
            "phone": service_details.get('phone_number')
        }
    
    return {}