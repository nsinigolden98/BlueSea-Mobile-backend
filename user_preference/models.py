from django.db import models
from django.contrib.auth import get_user_model

# Use get_user_model() to handle custom User models
User = get_user_model()


class UpdateUserModel(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to="profiles/", blank=True, null=True)
    nickname = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ("male", "Male"),
            ("female", "Female"),
            ("others", "Others"),
        ],
    )
    date_of_birth = models.DateField(blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    state = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=20, blank=True, null=True)
    street_address = models.CharField(max_length=100, blank=True, null=True)
    landmark = models.CharField(max_length=50, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    updated_on = models.DateTimeField(auto_now=True)
