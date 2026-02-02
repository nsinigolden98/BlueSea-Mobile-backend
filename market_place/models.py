import email
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.conf import settings

import uuid

User = get_user_model()




class TicketVendor(models.Model):
    BUSINESS_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('registered', 'Registered Business'),
        ('organizer', 'Event Organizer'),
    ]
    
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_vendors", null=True, blank=True)
    
    # Seller Identity
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, null=True, blank=True)
    legal_full_name = models.CharField(max_length=255, help_text="Legal full name from government ID", null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=300, unique=True, null=True, blank=True)
    brand_name = models.CharField(max_length=255, null=True, blank=True)
    
    # Accountability details
    residential_address = models.TextField(null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    
    # ID Information
    id_type = models.CharField(max_length=50, help_text="NIN, Passport, Driver's License", null=True, blank=True)
    id_document = models.FileField(
        upload_to='vendor_ids/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Upload ID document (PDF, JPEG, or PNG format)", null=True, blank=True
    )
    proof_of_address = models.FileField(
        upload_to='vendor_proof_of_address/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Utility bill or bank statement within last 3 months", null=True, blank=True
    )
    event_authorization = models.FileField(
        upload_to='vendor_event_auth/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True,
        blank=True,
        help_text="Optional: Authorization letter from event owner"
    )
    
    # Business & Event Information
    categories = models.CharField(
        max_length=500,
        help_text="Comma-separated list of categories: concerts, conferences, religious, sports, others", null=True, blank=True
    )
    monthly_volume = models.CharField(max_length=20, help_text="Estimated monthly ticket volume range", null=True, blank=True)
    business_description = models.TextField(help_text="Description of business model and typical events", null=True, blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20, 
        choices=VERIFICATION_STATUS_CHOICES, 
        default='pending', null=True, blank=True
    )
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.brand_name

    class Meta:
        verbose_name = "Ticket Vendor"
        verbose_name_plural = "Ticket Vendors"
        ordering = ['-created_at']


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
    CATEGORY_CHOICES = [
        ('Music', 'Music'),
        ('Conference', 'Conference'),
        ('Sports', 'Sports'),
        ('Networking', 'Networking'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(TicketVendor, on_delete=models.CASCADE, related_name="events")
    event_title = models.CharField(max_length=255)
    hosted_by = models.CharField(max_length=255, help_text="Name of the host/organizer")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    event_banner = models.ImageField(upload_to='event_banners/%Y/%m/%d/')
    ticket_image = models.ImageField(
        upload_to='ticket_images/%Y/%m/%d/', 
        null=True, 
        blank=True,
        help_text="Optional ticket design image"
    )
    event_date = models.DateTimeField()
    event_location = models.CharField(max_length=255)
    event_description = models.TextField(null=True, blank=True)
    is_free = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_title

    class Meta:
        ordering = ['-event_date']


class TicketType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(EventInfo, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=255, default='General Admission')  # e.g Regular, VIP, General Admission
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event.event_title} - {self.name}"


class IssuedTicket(models.Model):
    STATUS_CHOICES = [
        ('unused', 'Unused'),
        ('used', 'Used'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE, related_name="issued_tickets")
    event = models.ForeignKey(EventInfo, on_delete=models.CASCADE, related_name="issued_tickets")
    owner_name = models.CharField(max_length=255)
    owner_email = models.EmailField()
    purchased_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchased_tickets")
    qr_code = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unused')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket for {self.owner_name} - {self.event.event_title}"


class EventScanner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scanner_assignments")
    event = models.ForeignKey(EventInfo, on_delete=models.CASCADE, related_name="scanners")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Scanner {self.user.username} for Event {self.event.event_title}"

    class Meta:
        unique_together = ['user', 'event']