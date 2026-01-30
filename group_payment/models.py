from django.db import models
import uuid

class Group(models.Model):
    GROUP_STATUS=[
        ('active','active'),
        ('inactive', 'inactive')
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('accounts.Profile', related_name='created_groups', on_delete=models.CASCADE, null=True)
    service_type = models.CharField(max_length= 10, default='' )
    join_code = models.CharField(max_length= 10, default='' )
    sub_number = models.CharField(max_length= 20, default='')
    plan = models.CharField(max_length=100, default='')
    plan_type = models.CharField(max_length=100, blank=True, null=True, default='')
    target_amount= models.IntegerField(default=0)
    status=models.CharField(max_length=10,choices= GROUP_STATUS, default='active')
    invite_members= models.TextField(default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    
    group = models.ForeignKey(Group, related_name='members', on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.Profile', related_name='group_memberships', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} in {self.group.name} ({self.role})"