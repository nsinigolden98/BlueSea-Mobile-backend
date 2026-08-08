from django.db import models
from django.contrib.auth import get_user_model

# Use get_user_model() to handle custom User models
User = get_user_model()


class UpdateUserModel(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, )
    image = models.ImageField(upload_to='profiles/', blank=True, null=True)
