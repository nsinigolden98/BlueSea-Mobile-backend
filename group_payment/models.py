from django.db import models
import uuid
import secrets


def generate_join_code():
    return secrets.token_hex(3).upper()  # 6 characters


class Group(models.Model):
    SERVICE_TYPE_CHOICES = [
        ("airtime", "Airtime"),
        ("data", "Data"),
        ("lightbill", "Light Bill"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("partial", "Partially Paid"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("canceled", "Canceled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        "accounts.Profile",
        related_name="created_groups",
        on_delete=models.CASCADE,
        null=True,
    )
    service_type = models.CharField(
        max_length=20, choices=SERVICE_TYPE_CHOICES, default=""
    )
    sub_number = models.CharField(max_length=20, blank=True, default="")
    plan = models.CharField(max_length=100, blank=True, default="")
    plan_type = models.CharField(max_length=100, blank=True, null=True, default="")
    target_amount = models.IntegerField(default=0)
    current_amount = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    deadline = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    invite_members = models.TextField(default="")
    join_code = models.CharField(max_length=10, default=generate_join_code, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("locked", "Amount Locked"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    group = models.ForeignKey(Group, related_name="members", on_delete=models.CASCADE)
    user = models.ForeignKey(
        "accounts.Profile", related_name="group_memberships", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )
    locked_amount = models.IntegerField(default=0)
    paid_amount = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} in {self.group.name} ({self.role})"
