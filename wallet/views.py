from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Wallet
from .serializers import WalletSerializer


class WalletBalance(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet_user = Wallet.objects.get(user=request.user)
            wallet = wallet_user.balance

            return Response({"balance": wallet}, status=status.HTTP_200_OK)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)