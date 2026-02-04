# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated, IsAdminUser
# from rest_framework import status
# from django.db import transaction
# from django.shortcuts import get_object_or_404
# from django.http import HttpResponse
# from django.utils import timezone
# from decimal import Decimal
# import secrets
# import csv

# from loyalty_market.models import (
#     Reward, RedemptionTransaction
# )

# from wallet.models import Wallet
# from bonus.models import BonusPoint
# from drf_spectacular.utils import extend_schema, OpenApiParameter
# from drf_spectacular.types import OpenApiTypes

# import logging

# logger = logging.getLogger(__name__)


# # ============= EXISTING REWARD VIEWS =============

# class RewardListView(APIView):
#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         summary="List all rewards",
#         description="Get all available rewards in the loyalty marketplace",
#         responses={200: RewardSerializer(many=True)},
#         tags=['Loyalty Market']
#     )
#     def get(self, request):
#         rewards = Reward.objects.all()
#         serializer = RewardSerializer(rewards, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)


# class RewardDetailView(APIView):
#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         summary="Get reward details",
#         description="Retrieve details of a specific reward",
#         parameters=[
#             OpenApiParameter(name='reward_id', type=int, location=OpenApiParameter.PATH, description='Reward ID')
#         ],
#         responses={200: RewardSerializer, 404: OpenApiTypes.OBJECT},
#         tags=['Loyalty Market']
#     )
#     def get(self, request, reward_id):
#         try:
#             reward = Reward.objects.get(id=reward_id)
#         except Reward.DoesNotExist:
#             logger.error(f"Reward with id {reward_id} not found.")
#             return Response({"error": "Reward not found."}, status=status.HTTP_404_NOT_FOUND)

#         serializer = RewardSerializer(reward)
#         return Response(serializer.data, status=status.HTTP_200_OK)


# class UserPointsView(APIView):
#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         summary="Get user points balance",
#         description="Retrieve the authenticated user's total bonus points",
#         responses={200: OpenApiTypes.OBJECT},
#         tags=['Loyalty Market']
#     )
#     def get(self, request):
#         user = request.user
#         try:
#             bonus_point = BonusPoint.objects.get(user=user)
#             total_points = bonus_point.points
#         except BonusPoint.DoesNotExist:
#             total_points = 0

#         return Response({"total_points": total_points}, status=status.HTTP_200_OK)


# class AdminCreateRewardView(APIView):
#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         summary="Create new reward (Admin)",
#         description="Create a new reward in the loyalty marketplace (admin only)",
#         request=RewardSerializer,
#         responses={201: RewardSerializer, 400: OpenApiTypes.OBJECT},
#         tags=['Loyalty Market']
#     )
#     def post(self, request):
#         serializer = RewardSerializer(data=request.data)

#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         else:
#             logger.error(f"Reward creation failed: {serializer.errors}")
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class RedeemPointsView(APIView):
#     permission_classes = [IsAuthenticated]

#     @extend_schema(
#         summary="Redeem points for reward",
#         description="Redeem bonus points to claim a reward",
#         request=RedeemPointsSerializer,
#         responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
#         tags=['Loyalty Market']
#     )
#     def post(self, request):
#         serializer = RedeemPointsSerializer(data=request.data)

#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         points = Reward.objects.get(id=request.data.get('reward_id')).points_cost
#         # Implementation continues here...