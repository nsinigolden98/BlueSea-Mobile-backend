import logging

from django.conf import settings
from nomba import (
    Nomba,
    NombaAPIError,
    NombaAuthError,
    NombaError,
    NombaValidationError,
)

logger = logging.getLogger(__name__)

nomba = Nomba(
    client_id=settings.NOMBA_CLIENT_ID,
    account_id=settings.NOMBA_ACCOUNT_ID,
    client_secret=settings.NOMBA_SECRET_KEY,
    sandbox=settings.NOMBA_DEBUG,
)


def _err(e):
    if isinstance(e, NombaAPIError):
        return f"Nomba error {getattr(e, 'status_code', '')}: {getattr(e, 'code', '') or str(e)}"
    return str(e)


def create_checkout_order(order_reference, amount, email, callback_url=None):
    client_secret=settings.NOMBA_SECRET_KEY,
    """Create a Nomba hosted checkout order. Returns (True, checkoutLink) or (False, message)."""
    order = {
        "orderReference": order_reference,
        "amount": f"{amount:.2f}",
        "currency": "NGN",
        "customerEmail": email,
    }
    if callback_url:
        order["callbackUrl"] = callback_url
    try:
        resp = nomba.checkout.create_an_online_checkout_order(order=order)
    except (NombaValidationError, NombaAuthError, NombaAPIError, NombaError) as e:
        logger.warning(f"Nomba checkout order failed for {order_reference}: {e}")
        return False, _err(e)
    except Exception as e:
        logger.warning(f"Nomba checkout order failed for {order_reference}: {e}")
        return False, str(e)
    try:
        return True, resp.get("data").get("checkoutLink")
    except (KeyError, TypeError) as e:
        logger.warning(f"Nomba checkout order bad shape for {order_reference}: {resp}")
        return False, f"Unexpected checkout response: {e}"


def lookup_account_name(account_number, bank_code):
    """Resolve a bank account holder name. Returns {"success", "account_name"/"message"} like paystack.get_account_name."""
    try:
        resp = nomba.transfers.perform_bank_account_lookup(
            account_number=account_number, bank_code=bank_code
        )
    except (NombaValidationError, NombaAuthError, NombaAPIError, NombaError) as e:
        return {"success": False, "message": _err(e)}
    except Exception as e:
        return {"success": False, "message": str(e)}
    try:
        return {"success": True, "account_name": resp.get("data").get("accountName")}
    except (KeyError, TypeError):
        return {"success": False, "message": "Could not resolve account name"}


def create_nomba_virtual_account(account_ref, account_name):
    """Create a Nomba dedicated virtual account. Returns (True, data) or (False, message)."""
    try:
        resp = nomba.virtual_accounts.create_virtual_account(
            account_ref=account_ref, account_name=account_name
        )
    except (NombaValidationError, NombaAuthError, NombaAPIError, NombaError) as e:
        logger.warning(f"Nomba virtual account failed for {account_ref}: {e}")
        return False, _err(e)
    except Exception as e:
        logger.warning(f"Nomba virtual account failed for {account_ref}: {e}")
        return False, str(e)
    try:
        return True, resp.get("data")
    except (KeyError, TypeError):
        return False, "Unexpected virtual account response"


def transfer_to_bank(amount, account_number, account_name, bank_code, merchant_tx_ref, sender_name=None):
    """Transfer from the parent account to a bank account. Returns (True, data) or (False, message)."""
    try:
        resp = nomba.transfers.perform_bank_account_transfer_from_the_parent_account(
            amount=f"{amount:.2f}",
            account_number=account_number,
            account_name=account_name,
            bank_code=bank_code,
            merchant_tx_ref=merchant_tx_ref,
            sender_name=sender_name,
        )
    except (NombaValidationError, NombaAuthError, NombaAPIError, NombaError) as e:
        logger.warning(f"Nomba transfer failed for {merchant_tx_ref}: {e}")
        return False, _err(e)
    except Exception as e:
        logger.warning(f"Nomba transfer failed for {merchant_tx_ref}: {e}")
        return False, str(e)
    try:
        return True, resp.get("data")
    except (KeyError, TypeError):
        return False, "Unexpected transfer response"


def confirm_transaction(session_id):
    """Confirm a transaction status by Nomba sessionId. Returns (True, data) or (False, message)."""
    try:
        resp = nomba.transactions.confirm_a_transaction_s_status_by_session_id(session_id)
    except (NombaValidationError, NombaAuthError, NombaAPIError, NombaError) as e:
        return False, _err(e)
    except Exception as e:
        return False, str(e)
    try:
        return True, resp.get("data")
    except (KeyError, TypeError):
        return False, "Unexpected transaction response"
