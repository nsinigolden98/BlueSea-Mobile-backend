from django.db import models

# from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from transactions.models import WalletTransaction


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    locked_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal("0.00"))],
    )  # Add this field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet - {self.balance}"

    @property
    def available_balance(self):
        return self.balance

    def credit(self, amount, description="Credit", reference=None):
        if amount is None or Decimal(str(amount)) <= 0:
            raise ValueError("Amount must be positive")
        amount = Decimal(str(amount))
        from django.db import transaction as db_transaction
        from django.db.models import F

        with db_transaction.atomic():
            Wallet.objects.select_for_update().get(pk=self.pk)
            if (
                reference
                and WalletTransaction.objects.filter(reference=reference).exists()
            ):
                return
            Wallet.objects.filter(pk=self.pk).update(balance=F("balance") + amount)
            self.refresh_from_db(fields=["balance"])
            WalletTransaction.objects.create(
                wallet=self,
                amount=amount,
                transaction_type="CREDIT",
                description=description,
                reference=reference or str(uuid.uuid4()),
            )

    def debit(self, amount, description="Debit", reference=None):
        if amount is None or Decimal(str(amount)) <= 0:
            raise ValueError("Amount must be positive")
        amount = Decimal(str(amount))
        from django.db import transaction as db_transaction
        from django.db.models import F

        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            if (
                reference
                and WalletTransaction.objects.filter(reference=reference).exists()
            ):
                self.refresh_from_db(fields=["balance"])
                return
            if wallet.balance < amount:
                raise ValueError("Insufficient funds")
            Wallet.objects.filter(pk=self.pk).update(balance=F("balance") - amount)
            self.refresh_from_db(fields=["balance"])
            WalletTransaction.objects.create(
                wallet=self,
                amount=amount,
                transaction_type="DEBIT",
                description=description,
                reference=reference or str(uuid.uuid4()),
            )
