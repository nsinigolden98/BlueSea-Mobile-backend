from rest_framework import serializers
from .models import BonusPoint, BonusHistory, BonusCampaign, Referral


class BonusPointSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    redeemable_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = BonusPoint
        fields = [
            'id', 'user_email', 'points', 'lifetime_earned', 
            'lifetime_redeemed', 'redeemable_amount', 'last_daily_login', 
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_redeemable_amount(self, obj):
        return str(obj.points / 10)


class BonusHistorySerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = BonusHistory
        fields = [
            'id', 'transaction_type', 'transaction_type_display', 
            'points', 'reason', 'reason_display', 'description', 
            'reference', 'balance_before', 'balance_after', 
            'created_at', 'metadata'
        ]
        read_only_fields = fields


# class RedeemPointsSerializer(serializers.Serializer):
#     points = serializers.IntegerField(min_value=10)
    
#     def validate_points(self, value):
#         if value % 10 != 0:
#             raise serializers.ValidationError("Points must be in multiples of 10")
#         return value


class BonusCampaignSerializer(serializers.ModelSerializer):
    is_running = serializers.SerializerMethodField()
    
    class Meta:
        model = BonusCampaign
        fields = [
            'id', 'name', 'description', 'campaign_type', 
            'multiplier', 'bonus_amount', 'is_active', 
            'is_running', 'start_date', 'end_date'
        ]
        read_only_fields = fields
    
    def get_is_running(self, obj):
        return obj.is_running()


class ReferralSerializer(serializers.ModelSerializer):
    referrer_email = serializers.EmailField(source='referrer.email', read_only=True)
    referred_user_email = serializers.EmailField(source='referred_user.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Referral
        fields = [
            'id', 'referrer_email', 'referred_user_email', 
            'referral_code', 'status', 'status_display', 
            'bonus_awarded', 'first_transaction_completed', 
            'created_at', 'completed_at'
        ]
        read_only_fields = fields