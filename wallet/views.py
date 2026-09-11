from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

# Create your views here.
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Wallet


class WalletBalance(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Get wallet balance",
        description="Return the user's wallet balance, locked balance and available balance as formatted naira strings.",
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=["Wallet"],
    )
    def get(self, request):
        try:
            wallet_user = Wallet.objects.get(user=request.user)
            wallet = f"₦{wallet_user.balance:,.2f}"
            locked = f"₦{wallet_user.locked_balance:,.2f}"
            available = f"₦{wallet_user.available_balance:,.2f}"

            return Response(
                {
                    "balance": str(wallet),
                    "locked_balance": str(locked),
                    "available_balance": str(available),
                },
                status=status.HTTP_200_OK,
            )
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND
            )
