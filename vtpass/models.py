from django.db import models
from django.conf import settings
from wallet.models import Wallet
import uuid
from transactions.models import WalletTransaction


class VTUTransaction(models.Model):
    SERVICE_CHOICES = [
        ('AIRTIME', 'Airtime'),
        ('DATA', 'Data'),
        ('CABLE', 'Cable TV'),
        ('ELECTRICITY', 'Electricity'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vtu_transactions')
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='vtu_transactions')
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    recipient = models.CharField(max_length=100)
    request_id = models.CharField(max_length=64, unique=True)
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    reference = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    provider_txn_id = models.CharField(max_length=200, null=True, blank=True)
    provider_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.service_type} - {self.amount} - {self.status}"

    def mark_successful(self):
        self.status = 'SUCCESS'
        self.save()

    def mark_failed(self):
        self.status = 'FAILED'
        self.save()