from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone

from accounts.models import Profile

SERVICE_TYPE_CHOICES = [
    ('airtime', 'Airtime'),
    ('data', 'Data'),
]

class AutoTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auto_topups')
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('50.00'))])
    phone_number = models.CharField(max_length=20)
    network = models.CharField(max_length=20, blank=True, null=True)
    plan = models.CharField(max_length=100, blank=True, null=True)
    
    start_date = models.DateTimeField()
    repeat_days = models.IntegerField(default=0,help_text="0 for one-time, >0 for recurring every N days")
    is_active = models.BooleanField(default=True)
    next_run = models.DateTimeField()
    
    # Wallet locking
    is_locked = models.BooleanField(default=False)
    locked_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Tracking
    last_run = models.DateTimeField(blank=True, null=True)
    total_runs = models.IntegerField(default=0)
    failed_runs = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['next_run', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.service_type} - {self.amount}"
    
    def calculate_next_run(self):
        if self.repeat_days > 0:
            return self.next_run + timezone.timedelta(days=self.repeat_days)
        return None
    
    def lock_funds(self):
        wallet = self.user.wallet
        if wallet.balance >= self.amount:
            wallet.balance -= self.amount
            wallet.locked_balance = (wallet.locked_balance or Decimal('0.00')) + self.amount
            wallet.save()
            
            self.is_locked = True
            self.locked_amount = self.amount
            self.save()
            return True
        return False
    
    def unlock_funds(self):
        """Unlock funds back to user's wallet"""
        if self.is_locked and self.locked_amount > 0:
            wallet = self.user.wallet
            wallet.locked_balance = (wallet.locked_balance or Decimal('0.00')) - self.locked_amount
            wallet.balance += self.locked_amount
            wallet.save()
            
            self.is_locked = False
            self.locked_amount = Decimal('0.00')
            self.save()
            return True
        return False



class AutoTopUpHistory(models.Model):
    auto_topup = models.ForeignKey(AutoTopUp, on_delete=models.CASCADE, related_name='history')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('pending', 'Pending'),
        ]
    )
    vtu_reference = models.CharField(max_length=100, blank=True, null=True)
    vtu_response = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    executed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-executed_at']
        verbose_name_plural = 'Auto Top-Up Histories'
    
    def __str__(self):
        return f"{self.auto_topup.user.username} - {self.status} - {self.executed_at}"
