from venv import create
from django.db import models
from django.contrib.auth import get_user_model
from bonus.models import BonusPoint
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.conf import settings

import uuid

User = get_user_model()

class Reward(models.Model):
    FULFILMENT_CHOICES = [
        ('sms', 'SMS Delivery'),
        ('email', 'Email Delivery'),
        ('manual', 'Manual Fulfilment'),
        ('instant', 'Instant Delivery'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reward_user")
    title = models.CharField(max_length=255)
    description = models.TextField()
    image_url = models.URLField(null=True, blank=True)
    points_cost = models.IntegerField(default=0, validators=[MinValueValidator])
    category = models.CharField(max_length=255, null=True, blank=True)
    inventory = models.IntegerField(default=0, null=True, blank=True)
    availability_start = models.DateTimeField(auto_now=True)
    availability_end = models.DateTimeField(auto_now=True)
    fulfilment_type = models.CharField(max_length=20, choices=FULFILMENT_CHOICES, default='instant')
    polarity_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class RedemptionTransaction(models.Model):
    REDEMPTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name="redemption_user")
    reward_id = models.ForeignKey(Reward, on_delete=models.CASCADE, related_name="redemption_reward")
    points_deducted = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=REDEMPTION_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    fulfilment_payload = models.JSONField(null=True, blank=True)



class TicketVendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand_name = models.CharField(max_length=255)
    # Accountability details
    residential_address = models.TextField(null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



class VendorKYC(models.Model):
    KYC_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(TicketVendor, on_delete=models.CASCADE, related_name="vendor_kyc")
    document_type = models.CharField(max_length=100)
    document_number = models.CharField(max_length=100)
     # Change to FileField to accept direct uploads (PDF, JPEG, PNG)
    document_image = models.FileField(
        upload_to='kyc_documents/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Upload document (PDF, JPEG, or PNG format)"
    )
    
    proof_of_address = models.FileField(
        upload_to='kyc_proof_of_address/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True, 
        blank=True,
        help_text="Upload proof of address (PDF, JPEG, or PNG format)"
    )
    
    status = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"KYC for {self.vendor.brand_name}"


class EventInfo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(TicketVendor, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=255)
    event_image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    event_date = models.DateTimeField()
    event_location = models.CharField(max_length=255)
    event_description = models.TextField(null=True, blank=True)

    is_free = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)



class TicketType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(EventInfo, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=255)  # e.g Regular, VIP
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class IssuedTicket(models.Model):
    STATUS_CHOICES = [
        ('unused', 'Unused'),
        ('used', 'Used'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
    event = models.ForeignKey(EventInfo, on_delete=models.CASCADE)
    owner_name = models.CharField(max_length=255)
    owner_email = models.EmailField()
    purchased_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    qr_code = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unused')
    created_at = models.DateTimeField(auto_now_add=True)


class EventScanner(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(EventInfo, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Scanner {self.user.username} for Event {self.event.event_name}"