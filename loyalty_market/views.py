from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from loyalty_market.models import Reward, RedemptionTransaction
from loyalty_market.serializers import RewardSerializer, RedeemPointsSerializer
from bonus.models import BonusPoint

import logging

logger = logging.getLogger(__name__)

class RewardListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        rewards = Reward.objects.all()
        serializer = RewardSerializer(rewards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class RewardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reward_id):
        try:
            reward = Reward.objects.get(id=reward_id)
        except Reward.DoesNotExist:
            logger.error(f"Reward with id {reward_id} not found.")
            return Response({"error": "Reward not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RewardSerializer(reward)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            bonus_point = BonusPoint.objects.get(user=user)
            total_points = bonus_point.points
        except BonusPoint.DoesNotExist:
            total_points = 0

        return Response({"total_points": total_points}, status=status.HTTP_200_OK)


class AdminCreateRewardView(APIView):
    permission_classes = [IsAuthenticated]  
    # TODO: Add admin check

    def post(self, request):
        serializer = RewardSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Reward creation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RedeemPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RedeemPointsSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        points = Reward.objects.get(id=request.data.get('reward_id')).points_cost

        # try:
        #     bonus_point = BonusPoint.objects.get(user=request.user)
        #     if bonus_point.points < points:
        #         return Response({"error": "Insufficient points."}, status=status.HTTP_400_BAD_REQUEST)

        #     bonus_point.points -= points
        #     bonus_point.lifetime_redeemed += points
        #     bonus_point.save()

        #     RedemptionTransaction.objects.create(
        #         user=request.user,
        #         reward_id=request.data.get('reward_id'),
        #         points_redeemed=points
        #     )

        #     return Response({"message": "Points redeemed successfully."}, status=status.HTTP_200_OK)