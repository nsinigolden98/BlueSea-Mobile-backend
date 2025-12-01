from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from django.core.cache import cache
from django.db.models import F
from .models import Wallet
from .serializers import WalletSerializer, WalletBalanceSerializer
from drf_spectacular.utils import extend_schema, OpenApiResponse


class WalletBalance(GenericAPIView):

    permission_classes = [IsAuthenticated]
    serializer_class = WalletBalanceSerializer
    
    @extend_schema(
        summary="Get wallet balance",
        description="Retrieve the current wallet balance for the authenticated user. Results are cached for 30 seconds.",
        responses={
            200: WalletBalanceSerializer,
            404: OpenApiResponse(description="Wallet not found"),
        },
        tags=["Wallet"]
    )
    def get(self, request):
        user_id = request.user.id
        cache_key = f'wallet_balance_{user_id}'
        
        # Try to get from cache first (30 second cache)
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)
        
        try:
            wallet = Wallet.objects.only(
                'balance', 'locked_balance'
            ).select_related('user').get(user_id=user_id)
            
            # Format response
            response_data = {
                'balance': f"₦{wallet.balance:,.2f}",
                'raw_balance': wallet.balance,
                'available_balance': wallet.available_balance,
                'locked_balance': wallet.locked_balance or 0
            }
            
            # Cache for 30 seconds
            cache.set(cache_key, response_data, timeout=30)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )


