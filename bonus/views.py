from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction as db_transaction
from .models import BonusPoint, BonusHistory, BonusCampaign
from .serializers import (
    BonusPointSerializer, 
    BonusHistorySerializer, 
    RedeemPointsSerializer,
    BonusCampaignSerializer
)
from .utils import (
    redeem_points, 
    award_daily_login_bonus, 
    get_user_points_summary
)
import logging

logger = logging.getLogger(__name__)


class BonusPointsSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            summary = get_user_points_summary(request.user)
            return Response({
                'success': True,
                'data': summary
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting points summary for {request.user.email}: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve points summary'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BonusHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
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


class RedeemPointsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = RedeemPointsSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        points = serializer.validated_data['points']
        
        try:
            history, wallet_amount = redeem_points(
                user=request.user,
                points=points
            )
            
            return Response({
                'success': True,
                'message': f'Successfully redeemed {points} points for ₦{wallet_amount}',
                'data': {
                    'points_redeemed': points,
                    'wallet_amount': str(wallet_amount),
                    'new_balance': BonusPoint.objects.get(user=request.user).points
                }
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error redeeming points for {request.user.email}: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to redeem points'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClaimDailyLoginView(APIView):
    permission_classes = [IsAuthenticated]
    
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