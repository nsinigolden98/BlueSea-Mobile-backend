from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from decimal import Decimal


class AffiliateProfile(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_profile",
    )
    affiliate_name = models.CharField(
        max_length=30,
        unique=True,
        validators=[
            RegexValidator(
                r"^[A-Za-z0-9]+$",
                "Affiliate name can only contain letters and numbers.",
            )
        ],
        help_text="Unique affiliate name (letters and numbers only)",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Commission percentage of ticket sales",
    )
    facebook = models.URLField(null=True, blank=True)
    instagram = models.URLField(null=True, blank=True)
    twitter = models.URLField(null=True, blank=True)
    tiktok = models.URLField(null=True, blank=True)
    agreement_accepted = models.BooleanField(default=False)
    rejected_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.affiliate_name} ({self.status})"

    @property
    def is_approved(self):
        return self.status == "approved"

    def approve(self):
        self.status = "approved"
        self.rejected_reason = None
        self.save()

    def reject(self, reason):
        self.status = "rejected"
        self.rejected_reason = reason
        self.save()


class AffiliateLink(models.Model):
    affiliate = models.ForeignKey(
        AffiliateProfile, on_delete=models.CASCADE, related_name="links"
    )
    event = models.ForeignKey(
        "market_place.EventInfo",
        on_delete=models.CASCADE,
        related_name="affiliate_links",
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Commission percentage snapshot for this link",
    )
    clicks = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [["affiliate", "event"]]

    def __str__(self):
        return f"{self.affiliate.affiliate_name} -> {self.event.event_title}"

    def increment_clicks(self):
        self.clicks += 1
        self.save(update_fields=["clicks"])

    @property
    def link(self):
        return f"/events/{self.event.id}/?affiliate={self.affiliate.affiliate_name}"


class AffiliateSale(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("payable", "Payable"),
        ("paid", "Paid"),
        ("revoked", "Revoked"),
    ]

    affiliate = models.ForeignKey(
        AffiliateProfile, on_delete=models.CASCADE, related_name="sales"
    )
    link = models.ForeignKey(
        AffiliateLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    event = models.ForeignKey(
        "market_place.EventInfo",
        on_delete=models.CASCADE,
        related_name="affiliate_sales",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_sales",
    )
    issued_ticket = models.ForeignKey(
        "market_place.IssuedTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliate_sale",
        help_text="First ticket of the attributed purchase (for refund tracking)",
    )
    ticket_count = models.IntegerField(default=0)
    gross_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("2.00")
    )
    commission_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    payable_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.affiliate.affiliate_name} - {self.event.event_title} - {self.status}"
