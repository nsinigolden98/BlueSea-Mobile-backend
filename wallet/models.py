from django.db import models
# from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from transactions.models import WalletTransaction


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(Decimal('0.00'))])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet - {self.balance}"
    

    def credit(self, amount, description="Credit", reference=None):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        amount = Decimal(str(amount))
        
        self.balance += amount
        self.save()

        # create transaction record
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='CREDIT',
            description=description,
            reference=reference or str(uuid.uuid4())
        )

    def debit(self, amount, description="Debit", reference=None):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < Decimal(amount):
            raise ValueError("Insufficient funds")
        
        self.balance -= Decimal(amount)
        self.save()

        WalletTransaction.objects.create(
            wallet=self,
            amount=Decimal(amount),
            transaction_type='DEBIT',
            description=description,
            reference=reference or str(uuid.uuid4())
        )