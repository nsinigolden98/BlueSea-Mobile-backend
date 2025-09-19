from django.db import transaction
from django.utils import timezone
import uuid 
import logging
from .models import WalletTransaction, FundWallet
from wallet.models import Wallet

logger = logging.getLogger(__name__)

class WalletConfig:
    @staticmethod
    def user_wallet(user):
        """Create a wallet or Retrieve an existing User wallet"""
        wallet, created = Wallet.objects.get_or_create(user=user)
        if created:
            logger.info(f"Wallet created successfully for user {user.username}")
        return wallet
    
    @staticmethod
    def wallet_balance(user):
        wallet = WalletConfig.user_wallet(user)
        return wallet.balance
    

    @staticmethod
    @transaction.atomic
    def fund_wallet(user, amount, payment_reference, gateway_reference=None):
        try:
            wallet  = WalletConfig.get_or_create_wallet(user)

            # check for funding
            funds = FundWallet.objects.filter(payment_reference=payment_reference).first()

            if funds:
                if funds.status == 'COMPLETED':
                    raise ValueError("This payment reference has already been used.")
                funds.status = 'COMPLETED'
                funds.gateway_reference = gateway_reference
                funds.completed_at = timezone.now()
                funds.save()

            else:
                funds = FundWallet.objects.create(
                    user=user,
                    amount=amount,
                    payment_reference=payment_reference,
                    gateway_reference=gateway_reference,
                    status='COMPLETED',
                    completed_at=timezone.now()
                )

            # credit wallet
            wallet.credit(
                amount=amount,
                description="Wallet Funding",
                reference=payment_reference
            )

            logger.info(f"Wallet funded successfully for user {user.username} with amount {amount}")
            return wallet.balance
        except Exception as e:
            logger.error(f"Error funding wallet for user {user.username}: {str(e)}")
            raise

    # @staticmethod
    # @transaction.atomic
    # def debit_wa