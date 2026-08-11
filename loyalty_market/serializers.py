from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Reward, RedemptionTransaction
User = get_user_model()


class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = '__all__'
        required_fields = ('title', 'description', 'points_cost', 'category')
        read_only_fields = ('id', 'created_at', 'user')


class RewardListResponse(serializers.Serializer):
    count = serializers.IntegerField()
    rewards = RewardSerializer(many=True)

class RedemptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    reward = serializers.CharField()
    points_deducted = serializers.IntegerField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()

class RedemptionListResponse(serializers.Serializer):
    count = serializers.IntegerField()
    redemptions = RedemptionSerializer(many=True)


class RedeemPointsSerializer(serializers.Serializer):
    points = serializers.IntegerField(min_value=1)

    def validate_points(self, value):
        if value <= 0:
            raise serializers.ValidationError("Points must be a positive integer")
        return value

