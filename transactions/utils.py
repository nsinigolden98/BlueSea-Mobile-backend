# from django.db import transaction
# from django.utils import timezone
# import uuid 
# import logging
# from .models import WalletTransaction, FundWallet
# from wallet.models import Wallet
# from decimal import Decimal

# logger = logging.getLogger(__name__)

# class WalletConfig:
#     @staticmethod
#     def user_wallet(user):
#         """Create a wallet or Retrieve an existing User wallet"""
#         wallet, created = Wallet.objects.get_or_create(user=user)
#         if created:
#             logger.info(f"Wallet created successfully for user {user.username}")
#         return wallet
    
#     @staticmethod
#     def wallet_balance(user):
#         wallet = WalletConfig.user_wallet(user)
#         return wallet.balance
    

#     @staticmethod
#     @transaction.atomic
#     def fund_wallet(user, amount, payment_reference, gateway_reference=None):
#         try:
#             logger.info(f"Starting fund_wallet process for user {user.username if user else 'None'}")
            
#             # Ensure amount is Decimal
#             if not isinstance(amount, Decimal):
#                 amount = Decimal(str(amount))
            
#             logger.info(f"Amount: {amount}, Reference: {payment_reference}")
            
#             wallet = WalletConfig.user_wallet(user)
#             logger.info(f"Retrieved wallet for user {user.username if user else 'None'}")

#             # check for funding
#             funds = FundWallet.objects.filter(payment_reference=payment_reference).first()
#             logger.info(f"Found funding request: {funds}")

#             if funds:
#                 if funds.status == 'COMPLETED':
#                     logger.error(f"Payment reference {payment_reference} has already been used")
#                     raise ValueError("This payment reference has already been used.")
                
#                 logger.info(f"Updating existing funding request {payment_reference}")
#                 funds.status = 'COMPLETED'
#                 funds.gateway_reference = gateway_reference
#                 funds.completed_at = timezone.now()
#                 funds.save()

#             # credit wallet
#             logger.info(f"Crediting wallet for user {user.username if user else 'None'} with amount {amount}")
#             new_balance = wallet.credit(
#                 amount=amount,
#                 description="Wallet Funding",
#                 reference=payment_reference
#             )

#             logger.info(f"Wallet funded successfully for user {user.username if user else 'None'} with amount {amount}")
#             return new_balance
#         except Exception as e:
#             logger.error(f"Error funding wallet for user {user.username if user else 'None'}: {str(e)}", exc_info=True)
#             raise

#     @staticmethod
#     @transaction.atomic
#     def debit_walet_for_purchase(user, amount, sercive_typr, reference=None):
#         try:
#             wallet = WalletConfig.user_wallet(user)

#             if wallet.balance < amount:
#                 raise ValueError("Insufficient funds in wallet.")

#             # debit the wallet
#             new_balance = wallet.debit(
#                 amount=amount,
#                 description=f"Debit for {sercive_typr}",
#                 reference=reference or str(uuid.uuid4())
#             )
#             # transaction = WalletTransaction.objects.create(
#             #     wallet=wallet,
#             #     amount=amount,
#             #     transaction_type='DEBIT',
#             #     status='COMPLETED',
#             #     description=description,
#             #     reference=str(uuid.uuid4())
#             # )

#             logger.info(f"Wallet debited successfully for user {user.username} with amount {amount}")
#             return new_balance
#         except Exception as e:
#             logger.error(f"Error debiting wallet for user {user.username}: {str(e)}")
#             raise

#     @staticmethod
#     @transaction.atomic
#     def transaction_refund(user, amount, original_reference, reason="Refund"):
#         try:
#             wallet = WalletConfig.user_wallet(user)

#             refund_ref = f"REFUND-{original_reference}"

#             # credit the wallet
#             new_balance = wallet.credit(
#                 amount=amount,
#                 description=f"Refund for {reason}",
#                 reference=refund_ref
#             )

#             logger.info(f"Wallet refunded successfully for user {user.username} with amount {amount}")
#             return new_balance
#         except Exception as e:
#             logger.error(f"Error refunding wallet for user {user.username}: {str(e)}")
#             raise

#     @staticmethod
#     def transaction_history(user):
#         wallet = WalletConfig.user_wallet(user)
#         return wallet.transactions.all()