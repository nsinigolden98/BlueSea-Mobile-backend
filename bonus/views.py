from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction as db_transaction
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .models import BonusPoint, BonusHistory, BonusCampaign
from .serializers import (
    BonusPointSerializer, 
    BonusHistorySerializer, 
   # RedeemPointsSerializer,
    BonusCampaignSerializer
)
from .utils import (
    redeem_points, 
    award_daily_login_bonus, 
    user_points_summary
)
import logging
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__)


class BonusPointsSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get bonus points summary",
        description="Retrieve user's bonus points balance and statistics",
        responses={200: OpenApiTypes.OBJECT, 500: OpenApiTypes.OBJECT},
        tags=['Bonus & Rewards']
    )
    def get(self, request):
        try:
            # Try to get from cache first
            cache_key = f'bonus_summary_{request.user.id}'
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return Response({
                    'success': True,
                    'data': cached_data,
                    'cached': True
                }, status=status.HTTP_200_OK)
            
            # If not in cache, get from database
            summary = user_points_summary(request.user)
            
            # Cache for 5 minutes
            cache.set(cache_key, summary, timeout=300)
            
            return Response({
                'success': True,
                'data': summary,
                'cached': False
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting points summary for {request.user.email}: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve points summary'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BonusHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get bonus transaction history",
        description="Retrieve user's bonus points transaction history with pagination",
        parameters=[
            OpenApiParameter(name='type', type=str, description='Filter by transaction type', required=False),
            OpenApiParameter(name='page', type=int, description='Page number', required=False),
            OpenApiParameter(name='page_size', type=int, description='Items per page (default: 20)', required=False),
        ],
        responses={200: BonusHistorySerializer(many=True), 500: OpenApiTypes.OBJECT},
        tags=['Bonus & Rewards']
    )
    
    def get(self, request):
        try:
            history = BonusHistory.objects.filter(user=request.user)
            
            # Filter by transaction type if provided
            transaction_type = request.query_params.get('type')
            if transaction_type:
                history = history.filter(transaction_type=transaction_type)
            
            # Pagination
            page_size = int(request.query_params.get('page_size', 20))
            page = int(request.query_params.get('page', 1))
            start = (page - 1) * page_size
            end = start + page_size
            
            total_count = history.count()
            history = history[start:end]
            
            serializer = BonusHistorySerializer(history, many=True)
            
            return Response({
                'success': True,
                'count': total_count,
                'page': page,
                'page_size': page_size,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting history for {request.user.email}: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve history'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class RedeemPointsView(APIView):
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request):
#         serializer = RedeemPointsSerializer(data=request.data)
        
#         if not serializer.is_valid():
#             return Response({
#                 'success': False,
#                 'errors': serializer.errors
#             }, status=status.HTTP_400_BAD_REQUEST)
        
#         points = serializer.validated_data['points']
        
#         try:
#             history, wallet_amount = redeem_points(
#                 user=request.user,
#                 points=points
#             )
            
#             return Response({
#                 'success': True,
#                 'message': f'Successfully redeemed {points} points for ₦{wallet_amount}',
#                 'data': {
#                     'points_redeemed': points,
#                     'wallet_amount': str(wallet_amount),
#                     'new_balance': BonusPoint.objects.get(user=request.user).points
#                 }
#             }, status=status.HTTP_200_OK)
            
#         except ValueError as e:
#             return Response({
#                 'success': False,
#                 'error': str(e)
#             }, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.error(f"Error redeeming points for {request.user.email}: {str(e)}")
#             return Response({
#                 'success': False,
#                 'error': 'Failed to redeem points'
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClaimDailyLoginView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Claim daily login bonus",
        description="Claim daily login bonus points (once per day)",
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 500: OpenApiTypes.OBJECT},
        tags=['Bonus & Rewards']
    )
    
    def post(self, request):
        try:
            history = award_daily_login_bonus(request.user)
            
            if history:
                return Response({
                    'success': True,
                    'message': 'Daily login bonus claimed!',
                    'data': {
                        'points_earned': history.points,
                        'new_balance': history.balance_after
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'You have already claimed your daily bonus today'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error claiming daily bonus for {request.user.email}: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to claim daily bonus'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ActiveCampaignsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get active campaigns",
        description="Retrieve all currently active bonus campaigns",
        responses={200: BonusCampaignSerializer(many=True), 500: OpenApiTypes.OBJECT},
        tags=['Bonus & Rewards']
    )
    # Cache for 15 minutes
    @method_decorator(cache_page(60 * 15)) 
    def get(self, request):
        try:
            from django.utils import timezone
            
            campaigns = BonusCampaign.objects.filter(
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            )
            
            serializer = BonusCampaignSerializer(campaigns, many=True)
            
            return Response({
                'success': True,
                'count': campaigns.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting campaigns: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve campaigns'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)