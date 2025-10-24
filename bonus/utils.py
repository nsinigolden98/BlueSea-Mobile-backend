from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import BonusPoint, BonusHistory, BonusCampaign, Referral
from notifications.models import Notification
import logging

logger = logging.getLogger(__name__)


def award_points(user, points, reason, description, reference=None, metadata=None, created_by=None):
    """
    Award bonus points to a user and create history record
    """
    if points <= 0:
        raise ValueError("Points must be positive")
    
    try:
        with transaction.atomic():
            bonus_account, created = BonusPoint.objects.get_or_create(user=user)
            
            active_campaign = BonusCampaign.objects.filter(
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            ).first()
            
            # Apply campaign bonus if exists
            original_points = points
            if active_campaign:
                points = active_campaign.calculate_points(points)
                description += f" (Campaign: {active_campaign.name})"
            
            # Record balance before transaction
            balance_before = bonus_account.points
            
            # Add points to account
            bonus_account.add_points(points)
            
            # Create history record
            history = BonusHistory.objects.create(
                user=user,
                transaction_type='earned',
                points=points,
                reason=reason,
                description=description,
                reference=reference,
                balance_before=balance_before,
                balance_after=bonus_account.points,
                created_by=created_by,
                metadata=metadata or {}
            )
            
            # Send notification
            # send_points_notification(
            #     user=user,
            #     points=points,
            #     notification_type='earned',
            #     description=description
            # )
            
            logger.info(f"Awarded {points} points to {user.email} for {reason}")
            
            return history
            
    except Exception as e:
        logger.error(f"Error awarding points to {user.email}: {str(e)}")
        raise


def redeem_points(user, points, description="Points redeemed to wallet"):
    """
    Redeem bonus points and convert to wallet balance
    Conversion rate: 10 points = ₦1
    """

    # 10 points = ₦1
    CONVERSION_RATE = 10
    
    if points <= 0:
        raise ValueError("Points must be positive")
    
    if points % CONVERSION_RATE != 0:
        raise ValueError(f"Points must be in multiples of {CONVERSION_RATE}")
    
    try:
        with transaction.atomic():
            bonus_account = BonusPoint.objects.select_for_update().get(user=user)
            
            if bonus_account.points < points:
                raise ValueError(f"Insufficient points. You have {bonus_account.points} points.")
            
            wallet_amount = Decimal(points) / Decimal(CONVERSION_RATE)
            
            balance_before = bonus_account.points
            
            bonus_account.deduct_points(points)
            
            # Credit wallet
            user.wallet.credit(
                amount=wallet_amount,
                description=f"Bonus points redemption ({points} points)",
                reference=f"BP-REDEEM-{bonus_account.user.id}-{timezone.now().timestamp()}"
            )
            
            history = BonusHistory.objects.create(
                user=user,
                transaction_type='redeemed',
                points=points,
                reason=None,
                description=f"{description} - Converted to ₦{wallet_amount}",
                reference=f"BP-REDEEM-{bonus_account.user.id}",
                balance_before=balance_before,
                balance_after=bonus_account.points,
                metadata={'wallet_amount': str(wallet_amount), 'conversion_rate': CONVERSION_RATE}
            )
            
            # Send notification
            # send_points_notification(
            #     user=user,
            #     points=points,
            #     notification_type='redeemed',
            #     description=f"You redeemed {points} points for ₦{wallet_amount}"
            # )
            
            logger.info(f"User {user.email} redeemed {points} points for ₦{wallet_amount}")
            
            return history, wallet_amount
            
    except BonusPoint.DoesNotExist:
        raise ValueError("Bonus account not found")
    except Exception as e:
        logger.error(f"Error redeeming points for {user.email}: {str(e)}")
        raise


def award_vtu_purchase_points(user, purchase_amount, reference):
    """
    Award points for VTU purchase
    Rate: 1 point per ₦100 spent
    """
    POINTS_PER_100 = 1
    
    purchase_amount = Decimal(str(purchase_amount))
    points = int(purchase_amount / 100) * POINTS_PER_100
    
    if points > 0:
        return award_points(
            user=user,
            points=points,
            reason='vtu_purchase',
            description=f"VTU purchase bonus for ₦{purchase_amount} transaction",
            reference=reference,
            metadata={'purchase_amount': str(purchase_amount)}
        )
    
    return None


def award_referral_bonus(referrer, referred_user):
    """
    Award referral bonus when referred user completes first transaction
    """
    # Referral bonus set to 500
    REFERRAL_BONUS = 500
    
    try:
        referral = Referral.objects.get(
            referrer=referrer,
            referred_user=referred_user,
            status='pending'
        )
        
        # Award bonus
        history = award_points(
            user=referrer,
            points=REFERRAL_BONUS,
            reason='referral',
            description=f"Referral bonus for {referred_user.email} completing first transaction",
            reference=f"REF-{referral.id}",
            metadata={'referred_user_id': referred_user.id}
        )
        
        # Mark referral as completed
        referral.mark_completed()
        referral.bonus_awarded = True
        referral.save()
        
        return history
        
    except Referral.DoesNotExist:
        logger.warning(f"No referral record found for {referred_user.email}")
        return None


def award_daily_login_bonus(user):
    """
    Award daily login bonus
    
    Args:
        user: User instance
        
    Returns:
        BonusHistory instance or None if already claimed today
    """
    DAILY_LOGIN_BONUS = 10
    
    try:
        with transaction.atomic():
            bonus_account, created = BonusPoint.objects.get_or_create(user=user)
            
            # Check if user can claim daily login bonus
            if not bonus_account.can_claim_daily_login():
                logger.info(f"User {user.email} already claimed daily login bonus today")
                return None
            
            # Award points
            history = award_points(
                user=user,
                points=DAILY_LOGIN_BONUS,
                reason='daily_login',
                description="Daily login bonus",
                reference=f"DAILY-{user.id}-{timezone.now().date()}"
            )
            
            # Update last login date
            bonus_account.last_daily_login = timezone.now().date()
            bonus_account.save(update_fields=['last_daily_login'])
            
            return history
            
    except Exception as e:
        logger.error(f"Error awarding daily login bonus to {user.email}: {str(e)}")
        raise


# def send_points_notification(user, points, notification_type, description):
#     """
#     Helper function to send bonus points notification
    
#     Args:
#         user: User instance
#         points: Number of points
#         notification_type: 'earned' or 'redeemed'
#         description: Notification message
#     """
#     try:
#         if notification_type == 'earned':
#             title = f"You earned {points} bonus points!"
#             notif_type = 'info'
#         else:
#             title = f"{points} points redeemed"
#             notif_type = 'wallet'
        
#         Notification.objects.create(
#             user=user,
#             title=title,
#             message=description,
#             notification_type=notif_type
#         )
#     except Exception as e:
#         logger.error(f"Error sending notification to {user.email}: {str(e)}")


def user_points_summary(user):
    try:
        bonus_account = BonusPoint.objects.get(user=user)
        
        # Get recent history
        recent_history = BonusHistory.objects.filter(user=user)[:10]
        
        # Calculate redeemable amount
        redeemable_amount = Decimal(bonus_account.points) / 10
        
        return {
            'current_points': bonus_account.points,
            'lifetime_earned': bonus_account.lifetime_earned,
            'lifetime_redeemed': bonus_account.lifetime_redeemed,
            'redeemable_amount': str(redeemable_amount),
            'can_claim_daily_login': bonus_account.can_claim_daily_login(),
            'last_daily_login': bonus_account.last_daily_login,
            'recent_history': [
                {
                    'type': h.transaction_type,
                    'points': h.points,
                    'description': h.description,
                    'date': h.created_at
                } for h in recent_history
            ]
        }
    except BonusPoint.DoesNotExist:
        return {
            'current_points': 0,
            'lifetime_earned': 0,
            'lifetime_redeemed': 0,
            'redeemable_amount': '0.00',
            'can_claim_daily_login': True,
            'last_daily_login': None,
            'recent_history': []
        }