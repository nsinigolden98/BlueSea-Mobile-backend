from celery import shared_task
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging
from .models import AutoTopUp, AutoTopUpHistory
from payments.vtpass import generate_reference_id, top_up
from payments.vtpass import mtn_dict, airtel_dict, glo_dict, etisalat_dict

from notifications.utils import send_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_auto_topups(self):

    now = timezone.now()
    
    # Get all active auto top-ups that are due
    due_topups = AutoTopUp.objects.filter(is_active=True, next_run__lte=now, is_locked=True).select_related('user__wallet')
    
    logger.info(f"Found {due_topups.count()} due auto top-ups")
    
    for auto_topup in due_topups:
        try:
            execute_auto_topup.delay(auto_topup.id)
        except Exception as e:
            logger.error(f"Error queuing auto top-up {auto_topup.id}: {str(e)}")
    
    return f"Processed {due_topups.count()} auto top-ups"


@shared_task(bind=True, max_retries=3)
def execute_auto_topup(self, auto_topup_id):
    try:
        auto_topup = AutoTopUp.objects.select_related('user__wallet').get(id=auto_topup_id)
    except AutoTopUp.DoesNotExist:
        logger.error(f"AutoTopUp {auto_topup_id} not found")
        return
    
    with transaction.atomic():
        # Double check it's still active and locked
        if not auto_topup.is_active or not auto_topup.is_locked:
            logger.warning(f"AutoTopUp {auto_topup_id} is not active or locked")
            return
        
        request_id = generate_reference_id()
        history = AutoTopUpHistory.objects.create(
            auto_topup=auto_topup,
            amount=auto_topup.amount,
            status='pending'
        )
        
        try:
            vtu_data = vtu_data(auto_topup, request_id)
            
            vtu_response = top_up(vtu_data)
            
            if vtu_response.get("response_description") == "TRANSACTION SUCCESSFUL":
                wallet = auto_topup.user.wallet
                wallet.locked_balance -= auto_topup.locked_amount
                wallet.save()
                
                history.status = 'success'
                history.vtu_reference = vtu_response.get('requestId')
                history.vtu_response = vtu_response
                history.save()
                
                auto_topup.last_run = timezone.now()
                auto_topup.total_runs += 1
                auto_topup.is_locked = False
                auto_topup.locked_amount = Decimal('0.00')
                
                if auto_topup.repeat_days > 0:
                    next_run = auto_topup.calculate_next_run()
                    if next_run:
                        auto_topup.next_run = next_run
                        # Lock funds for next run
                        if not auto_topup.lock_funds():
                            auto_topup.is_active = False
                            send_notification(
                                user=auto_topup.user,
                                title="Auto Top-Up Deactivated",
                                message=f"Your {auto_topup.service_type} auto top-up has been deactivated due to insufficient funds.",
                                notification_type='warning'
                            )
                    else:
                        auto_topup.is_active = False
                else:
                    auto_topup.is_active = False
                
                auto_topup.save()
                
                # Send success notification
                send_notification(
                    user=auto_topup.user,
                    title="Auto Top-Up Successful",
                    message=f"Your {auto_topup.service_type} top-up of ₦{auto_topup.amount} to {auto_topup.phone_number} was successful.",
                    notification_type='success'
                )
                
                logger.info(f"Auto top-up {auto_topup_id} executed successfully")
                
            else:
                # VTU API failed - unlock funds
                topup_failure(auto_topup, history, vtu_response)
                
        except Exception as e:
            logger.error(f"Error executing auto top-up {auto_topup_id}: {str(e)}")
            topup_failure(
                auto_topup,
                history,
                {'error': str(e)}
            )
            raise self.retry(exc=e, countdown=60)


def vtu_data(auto_topup, request_id):
    if auto_topup.service_type == 'airtime':
        return {
            "request_id": request_id,
            "serviceID": auto_topup.network,
            "amount": int(auto_topup.amount),
            "phone": auto_topup.phone_number
        }
    
    elif auto_topup.service_type == 'data':
        plan_dicts = {
            'mtn': mtn_dict,
            'airtel': airtel_dict,
            'glo': glo_dict,
            'etisalat': etisalat_dict
        }
        
        plan_dict = plan_dicts.get(auto_topup.network, {})
        plan_info = plan_dict.get(auto_topup.plan, [None, auto_topup.amount])
        
        variation_code = plan_info[0] if plan_info[0] else auto_topup.plan
        amount = plan_info[1]
        
        return {
            "request_id": request_id,
            "serviceID": f"{auto_topup.network}-data",
            "billerCode": auto_topup.phone_number,
            "variation_code": variation_code,
            "amount": int(amount),
            "phone": auto_topup.phone_number
        }


def topup_failure(auto_topup, history, vtu_response):
    auto_topup.unlock_funds()
    
    # Update history
    history.status = 'failed'
    history.error_message = vtu_response.get('error', 'VTU API failed')
    history.vtu_response = vtu_response
    history.save()
    
    # Update auto top-up
    auto_topup.failed_runs += 1
    
    # Deactivate after 3 consecutive failures
    if auto_topup.failed_runs >= 3:
        auto_topup.is_active = False
        send_notification(
            user=auto_topup.user,
            title="Auto Top-Up Deactivated",
            message=f"Your {auto_topup.service_type} auto top-up has been deactivated after 3 failed attempts.",
            notification_type='error'
        )
    
    auto_topup.save()
    
    # Send failure notification
    send_notification(
        user=auto_topup.user,
        title="Auto Top-Up Failed",
        message=f"Your {auto_topup.service_type} top-up of ₦{auto_topup.amount} failed. Funds have been unlocked.",
        notification_type='error'
    )