from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Reward, RedemptionTransaction
from .serializers import RewardSerializer
from bonus.models import BonusPoint


class RewardListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rewards = Reward.objects.filter(inventory__gt=0).order_by("-created_at")
        serializer = RewardSerializer(rewards, many=True)
        return Response(
            {"count": rewards.count(), "rewards": serializer.data},
            status=status.HTTP_200_OK,
        )


class RewardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reward_id):
        reward = get_object_or_404(Reward, id=reward_id)
        serializer = RewardSerializer(reward)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RedeemRewardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reward_id):
        reward = get_object_or_404(Reward, id=reward_id)

        # Check inventory
        if reward.inventory and reward.inventory <= 0:
            return Response(
                {"error": "This reward is out of stock"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check user's points
        try:
            bonus_points = BonusPoint.objects.get(user=request.user)
        except BonusPoint.DoesNotExist:
            return Response(
                {"error": "You do not have any bonus points"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if bonus_points.points < reward.points_cost:
            return Response(
                {
                    "error": f"Insufficient points. You need {reward.points_cost} points but have {bonus_points.points}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deduct points and create redemption
        with transaction.atomic():
            bonus_points.deduct_points(reward.points_cost)

            redemption = RedemptionTransaction.objects.create(
                user_id=request.user,
                reward_id=reward,
                points_deducted=reward.points_cost,
                status="completed",
                fulfilment_payload={
                    "fulfilment_type": reward.fulfilment_type,
                    "delivery_info": request.data.get("delivery_info", ""),
                },
            )

            # Decrease inventory
            if reward.inventory:
                reward.inventory -= 1
                reward.save()

        return Response(
            {
                "success": True,
                "message": "Reward redeemed successfully",
                "redemption": {
                    "id": str(redemption.id),
                    "reward": reward.title,
                    "points_deducted": redemption.points_deducted,
                    "status": redemption.status,
                    "created_at": redemption.created_at,
                },
            },
            status=status.HTTP_200_OK,
        )


class UserRedemptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        redemptions = RedemptionTransaction.objects.filter(
            user_id=request.user
        ).order_by("-created_at")

        results = []
        for r in redemptions:
            results.append(
                {
                    "id": str(r.id),
                    "reward": r.reward_id.title if r.reward_id else "Unknown",
                    "points_deducted": r.points_deducted,
                    "status": r.status,
                    "created_at": r.created_at,
                }
            )

        return Response(
            {"count": redemptions.count(), "redemptions": results},
            status=status.HTTP_200_OK,
        )
