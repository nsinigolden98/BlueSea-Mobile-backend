from django.db import models
from django.contrib.auth import get_user_model
from models import Group, GroupMember

User = get_user_model()

class GroupPayment(models.Model):
    PAYMENT_TYPES = [
        ('airtime', 'Airtime'),
        ('data', 'Data'),
        ('electricity', 'Electricity'),
        ('dstv', 'DSTV'),
        ('gotv', 'GOTV'),
        ('startimes', 'Startimes'),
        ('showmax', 'ShowMax'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='payments')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    service_details = models.JSONField()  # Store phone number, meter number, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    vtu_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.group.name} - {self.payment_type} - ₦{self.total_amount}"


class GroupPaymentContribution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    group_payment = models.ForeignKey(GroupPayment, on_delete=models.CASCADE, related_name='contributions')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.member.user.get_full_name()} - ₦{self.amount}"