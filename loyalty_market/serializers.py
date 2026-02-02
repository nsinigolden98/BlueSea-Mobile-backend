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


class RedeemPointsSerializer(serializers.Serializer):
    points = serializers.IntegerField(min_value=1)

    def validate_points(self, value):
        if value <= 0:
            raise serializers.ValidationError("Points must be a positive integer")
        return value

