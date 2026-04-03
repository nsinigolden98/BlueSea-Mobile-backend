from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from payments.models import (
    AirtimeTopUp, MTNDataTopUp, AirtelDataTopUp, 
    GloDataTopUp, EtisalatDataTopUp, ElectricityPayment,
    DSTVPayment, GOTVPayment, StartimesPayment, ShowMaxPayment
)
from .models import BonusPoint, Referral
from .utils import award_vtu_purchase_points, award_referral_bonus
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_bonus_account(sender, instance, created, **kwargs):
    """Create bonus account when user is created"""
    if created:
        BonusPoint.objects.get_or_create(user=instance)
        logger.info(f"Created bonus account for {instance.email}")


# VTU Purchase Signals
@receiver(post_save, sender=AirtimeTopUp)
def award_airtime_bonus(sender, instance, created, **kwargs):
    """Award bonus points for airtime purchase"""
    if created and hasattr(instance, '_user'):
        try:
            award_vtu_purchase_points(
                user=instance._user,
                purchase_amount=instance.amount,
                reference=instance.request_id
            )
        except Exception as e:
            logger.error(f"Error awarding airtime bonus: {str(e)}")


@receiver(post_save, sender=MTNDataTopUp)
@receiver(post_save, sender=AirtelDataTopUp)
@receiver(post_save, sender=GloDataTopUp)
@receiver(post_save, sender=EtisalatDataTopUp)
def award_data_bonus(sender, instance, created, **kwargs):
    """Award bonus points for data purchase"""
    if created and hasattr(instance, '_user'):
        try:
            # Extract amount from plan (you'll need to adjust based on your plan structure)
            # This is a placeholder - adjust based on your dictionaries
            amount = 0  # Parse from plan or pass separately
            if amount > 0:
                award_vtu_purchase_points(
                    user=instance._user,
                    purchase_amount=amount,
                    reference=instance.request_id
                )
        except Exception as e:
            logger.error(f"Error awarding data bonus: {str(e)}")


@receiver(post_save, sender=ElectricityPayment)
def award_electricity_bonus(sender, instance, created, **kwargs):
    """Award bonus points for electricity payment"""
    if created and hasattr(instance, '_user'):
        try:
            award_vtu_purchase_points(
                user=instance._user,
                purchase_amount=instance.amount,
                reference=instance.request_id
            )
        except Exception as e:
            logger.error(f"Error awarding electricity bonus: {str(e)}")