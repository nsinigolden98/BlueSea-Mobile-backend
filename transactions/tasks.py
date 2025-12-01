from celery import shared_task
from django.db import transaction as db_transaction
from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal
import logging
from .models import FundWallet, WalletTransaction
from wallet.models import Wallet
from notifications.utils import send_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_wallet_funding(self, funding_id, webhook_data):
    try:
        with db_transaction.atomic():
            # Get funding request with lock
            funding_request = FundWallet.objects.select_for_update().get(
                id=funding_id,
                status='PENDING'
            )
            
            reference = webhook_data.get('reference')
            raw_amount = Decimal(str(webhook_data.get('amount', '0')))
            amount = raw_amount / Decimal('100')  # Convert from kobo to naira
            
            # Get wallet with lock
            try:
                wallet = Wallet.objects.select_for_update().get(user=funding_request.user)
            except Wallet.DoesNotExist:
                logger.error(f"Wallet not found for user: {funding_request.user.email}")
                funding_request.status = 'FAILED'
                funding_request.save()
                return {
                    'success': False,
                    'error': 'Wallet not found'
                }
            
            # Verify amount
            request_amount = Decimal(str(funding_request.amount))
            if abs(request_amount - amount) > Decimal('0.01'):
                logger.error(f"Amount mismatch - Expected: {request_amount}, Got: {amount}")
                funding_request.status = 'FAILED'
                funding_request.save()
                return {
                    'success': False,
                    'error': f'Amount mismatch. Expected {request_amount}, got {amount}'
                }
            
            # Update status to processing
            funding_request.status = 'PROCESSING'
            funding_request.save()
            
            # Update wallet balance
            old_balance = wallet.balance
            wallet.balance += amount
            wallet.save(update_fields=['balance', 'updated_at'])
            
            # Create transaction record
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type='CREDIT',
                description="Wallet Funding",
                reference=reference
            )
            
            # Update funding request status
            funding_request.status = 'COMPLETED'
            funding_request.completed_at = timezone.now()
            funding_request.save()
            
            # Clear wallet balance cache
            cache.delete(f'wallet_balance_{funding_request.user.id}')
            
            logger.info(
                f"Wallet funded successfully. User: {funding_request.user.email}, "
                f"Old balance: {old_balance}, New balance: {wallet.balance}"
            )
            
            # Send notification
            send_notification(
                user=funding_request.user,
                title="Wallet Funded Successfully",
                message=f"Your wallet has been credited with ₦{amount:,.2f}. New balance: ₦{wallet.balance:,.2f}",
                notification_type='success'
            )
            
            return {
                'success': True,
                'old_balance': str(old_balance),
                'new_balance': str(wallet.balance),
                'amount': str(amount)
            }
            
    except FundWallet.DoesNotExist:
        logger.error(f"FundWallet {funding_id} not found or already processed")
        return {
            'success': False,
            'error': 'Funding request not found or already processed'
        }
    except Exception as e:
        logger.error(f"Error processing wallet funding: {str(e)}", exc_info=True)
        
        # Mark as failed
        try:
            funding_request = FundWallet.objects.get(id=funding_id)
            funding_request.status = 'FAILED'
            funding_request.save()
        except:
            pass
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def clean_pending_fundings():

    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(hours=24)
    
    expired_fundings = FundWallet.objects.filter(
        status='PENDING',
        created_at__lt=cutoff_time
    )
    
    count = expired_fundings.count()
    expired_fundings.update(status='EXPIRED')
    
    logger.info(f"Marked {count} old pending fundings as expired")
    return f"Cleaned up {count} expired fundings"