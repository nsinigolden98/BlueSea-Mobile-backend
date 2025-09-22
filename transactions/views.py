from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from decimal import Decimal
from rest_framework.views import APIView
from .models import WalletTransaction, FundWallet
from .serializers import WalletTransactionSerializer, WalletFundingSerializer
from wallet.models import Wallet
from wallet.serializers import WalletSerializer
from .utils import WalletConfig


class GetWalletTransaction(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            wallet_balance = WalletConfig.transaction_history(user)
            return Response({"message": str(wallet_balance)}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InitializeFunding(APIView):
    