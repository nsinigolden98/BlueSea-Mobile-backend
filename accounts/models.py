from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import make_password, check_password

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)
    

class Profile(AbstractUser):
    email = models.EmailField(max_length=300, unique=True)
    surname = models.CharField(max_length=100, blank=True)
    other_names = models.CharField(max_length=100,blank=True)
    phone = models.CharField(max_length=200, null=True, blank=True)
    image = models.ImageField(null=True, blank=True)
    verification_code = models.CharField(null=True,max_length=100)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    role = models.CharField(max_length=200, default="user")
    email_verified = models.BooleanField(default=False)
    transaction_pin = models.CharField(max_length=255, null=True, blank=True)
    pin_is_set = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    username = None

    def __str__(self) -> str:
        return self.email

    def get_profile_picture(self):
        if self.image:
            return self.image.url
    
    def get_full_name(self):
        return f"{self.first_name}, {self.last_name}"
    
    def set_transaction_pin(self, pin):
        self.transaction_pin = make_password(str(pin))
        self.pin_is_set = True
        self.save()

    def verify_transaction_pin(self, pin):
        if not self.pin_is_set or self.transaction_pin:
            return check_password(str(pin), self.transaction_pin)

# @receiver(post_save, sender=settings.AUTH_USER_MODEL)
# def create_auth_token(sender, instance= None, created=False, **kwargs):
#     if created:
#         Token.objects.create(user=instance)
        # Wallet.objects.create(user=instance)


class EmailVerification(models.Model):
    email = models.EmailField(unique=True)
    otp = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class ResetPassword(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    otp = models.IntegerField()
    timestamp = models.DateTimeField(default=timezone.now)


    def __str__(self) -> str:
        return self.profile.email
    

class ResetPasswordValuationToken(models.Model):
    reset_token = models.CharField(max_length=200)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.reset_token