import uuid
import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from django.db import transaction as db_transaction
from decimal import Decimal
from .models import VTUTransaction
from wallet.models import Walletet
from transactions.models import WalletTransaction

VTPASS_BASE = settings.VTPASS_BASE_URL
VTPASS_EMAIL = settings.VTPASS_EMAIL
VTPASS_PASSWORD = settings.VTPASS_PASSWORD