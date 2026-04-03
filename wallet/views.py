from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Wallet
from .serializers import WalletSerializer

# Create your views here.
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
from .models import Wallet
from transactions.models import WalletTransaction, FundWallet
from .serializers import WalletSerializer
from transactions.serializers import WalletTransactionSerializer


class WalletBalance(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet_user = Wallet.objects.get(user=request.user)
            wallet = f"₦{wallet_user.balance:,.2f}"

            return Response({"balance": str(wallet)}, status=status.HTTP_200_OK)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)
        

