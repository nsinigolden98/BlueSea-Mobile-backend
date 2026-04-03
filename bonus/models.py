from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone

User = get_user_model()


class BonusPoint(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bonus_points')
    points = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    lifetime_earned = models.IntegerField(default=0, help_text="Total points earned over lifetime")
    lifetime_redeemed = models.IntegerField(default=0, help_text="Total points redeemed over lifetime")
    last_daily_login = models.DateField(null=True, blank=True, help_text="Last date user claimed daily login points")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-points']

    def __str__(self):
        return f"{self.user.email} - {self.points} points"

    def add_points(self, amount):
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        self.points += amount
        self.lifetime_earned += amount
        self.save(update_fields=['points', 'lifetime_earned', 'updated_at'])

    def deduct_points(self, amount):
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        if self.points < amount:
            raise ValueError("Insufficient points balance")
        self.points -= amount
        self.lifetime_redeemed += amount
        self.save(update_fields=['points', 'lifetime_redeemed', 'updated_at'])

    def can_claim_daily_login(self):
        if not self.last_daily_login:
            return True
        return self.last_daily_login < timezone.now().date()


class BonusHistory(models.Model):
    TRANSACTION_TYPES = [
        ('earned', 'Earned'),
        ('redeemed', 'Redeemed'),
        ('adjusted', 'Admin Adjustment'),
        ('expired', 'Expired'),
        ('reversed', 'Reversed'),
    ]

    EARNING_REASONS = [
        ('vtu_purchase', 'VTU Purchase'),
        ('referral', 'Referral Bonus'),
        ('daily_login', 'Daily Login'),
        ('campaign', 'Campaign Bonus'),
        ('admin_award', 'Admin Award'),
        ('signup_bonus', 'Signup Bonus'),
        ('milestone', 'Milestone Reward'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bonus_history')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    points = models.IntegerField()
    reason = models.CharField(max_length=50, choices=EARNING_REASONS, null=True, blank=True)
    description = models.TextField(help_text="Detailed description of the transaction")
    reference = models.CharField(max_length=100, null=True, blank=True, help_text="Related transaction reference")
    balance_before = models.IntegerField(help_text="Points balance before transaction")
    balance_after = models.IntegerField(help_text="Points balance after transaction")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonus_adjustments', help_text="Admin user who made the adjustment")
    metadata = models.JSONField(null=True, blank=True, help_text="Additional data (e.g., purchase amount, campaign info)")

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Bonus Histories"

    def __str__(self):
        return f"{self.user.email} - {self.transaction_type} - {self.points} pts"


class BonusCampaign(models.Model):
    CAMPAIGN_TYPES = [
        ('multiplier', 'Points Multiplier'),
        ('fixed_bonus', 'Fixed Bonus'),
        ('percentage_bonus', 'Percentage Bonus'),
    ]

    name = models.CharField(max_length=200, help_text="Campaign name")
    description = models.TextField()
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES, default='multiplier')
    multiplier = models.DecimalField(max_digits=3, decimal_places=1, default=1.0, help_text="Points multiplier (e.g., 2.0 for double points)")
    bonus_amount = models.IntegerField(default=0, help_text="Fixed bonus points or percentage bonus")
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date.date()} to {self.end_date.date()})"

    def is_running(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    def calculate_points(self, base_points):
        if not self.is_running():
            return base_points

        if self.campaign_type == 'multiplier':
            return int(base_points * self.multiplier)
        elif self.campaign_type == 'fixed_bonus':
            return base_points + self.bonus_amount
        elif self.campaign_type == 'percentage_bonus':
            return base_points + int(base_points * self.bonus_amount / 100)
        
        return base_points



class Referral(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]

    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral')
    referral_code = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    bonus_awarded = models.BooleanField(default=False)
    first_transaction_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.referrer.email} referred {self.referred_user.email}"

    def mark_completed(self):
        if not self.bonus_awarded:
            self.status = 'completed'
            self.first_transaction_completed = True
            self.completed_at = timezone.now()
            self.save()
