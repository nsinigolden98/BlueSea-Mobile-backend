from django.db import models
from django.contrib.auth import get_user_model
from bonus.models import BonusPoint
from django.core.validators import MinValueValidator

import uuid

User = get_user_model()

class Reward(models.Model):
    FULFILMENT_CHOICES = [
        ('sms', 'SMS Delivery'),
        ('email', 'Email Delivery'),
        ('manual', 'Manual Fulfilment'),
        ('instant', 'Instant Delivery'),
    ]
    id = models.UUIDField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reward user")
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
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name="redemption user")
    reward_id = models.ForeignKey(Reward, on_delete=models.CASCADE, related_name="redemption reward")
    points_deducted = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=REDEMPTION_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    fulfilment_payload = models.JSONField(null=True, blank=True)