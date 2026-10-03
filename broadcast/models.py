from django.conf import settings
from django.db import models


class Broadcast(models.Model):
    KIND_CHOICES = (
        ("new_month", "New Month"),
        ("important", "Important"),
        ("announcement", "Announcement"),
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("partial", "Partial"),
        ("failed", "Failed"),
    )

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    email_subject = models.CharField(max_length=200)
    template = models.CharField(max_length=200)
    month_key = models.CharField(max_length=7, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    total = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="broadcasts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} - {self.title} - {self.status}"
