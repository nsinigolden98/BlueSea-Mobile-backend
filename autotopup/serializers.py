from rest_framework import serializers
from django.utils import timezone
from .models import AutoTopUp, AutoTopUpHistory


class AutoTopUpSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    transaction_pin = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = AutoTopUp
        fields = [
            'id', 'service_type', 'amount', 'phone_number', 'network', 'plan',
            'start_date', 'repeat_days', 'is_active', 'next_run', 'is_locked',
            'locked_amount', 'last_run', 'total_runs', 'failed_runs',
            'created_at', 'updated_at', 'available_balance', 'transaction_pin'
        ]
        read_only_fields = [
            'id', 'next_run', 'is_locked', 'locked_amount', 'last_run', 'total_runs',
            'failed_runs', 'created_at', 'updated_at', 'available_balance'
        ]
    
    def get_available_balance(self, obj):
        return str(obj.user.wallet.available_balance)
    
    def validate(self, data):
        # Validate start_date is not in the past
        if data.get('start_date') and data['start_date'] < timezone.now():
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be in the past'
            })
        
        # Validate service_type specific fields
        service_type = data.get('service_type')
        if service_type == 'airtime' and not data.get('network'):
            raise serializers.ValidationError({
                'network': 'Network is required for airtime top-up'
            })
        
        if service_type == 'data':
            if not data.get('network'):
                raise serializers.ValidationError({
                    'network': 'Network is required for data top-up'
                })
            if not data.get('plan'):
                raise serializers.ValidationError({
                    'plan': 'Plan is required for data top-up'
                })
        
        # Validate amount
        amount = data.get('amount')
        if amount and amount < 50:
            raise serializers.ValidationError({
                'amount': 'Minimum amount is ₦50'
            })
        
        return data
    
    def validate_phone_number(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits')
        if len(value) < 10 or len(value) > 11:
            raise serializers.ValidationError('Phone number must be 10 or 11 digits')
        return value


class AutoTopUpCreateSerializer(AutoTopUpSerializer):    
    def validate(self, data):
        data = super().validate(data)
        
        user = self.context['request'].user
        amount = data.get('amount')
        
        if user.wallet.balance < amount:
            raise serializers.ValidationError({
                'amount': f'Insufficient funds. Available balance: ₦{user.wallet.available_balance}'
            })
        
        return data
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        
        # Automatically set next_run to start_date if not provided
        if 'next_run' not in validated_data:
            validated_data['next_run'] = validated_data['start_date']
        
        return super().create(validated_data)


class AutoTopUpHistorySerializer(serializers.ModelSerializer):
    service_type = serializers.CharField(source='auto_topup.service_type', read_only=True)
    phone_number = serializers.CharField(source='auto_topup.phone_number', read_only=True)
    
    class Meta:
        model = AutoTopUpHistory
        fields = [
            'id', 'service_type', 'phone_number', 'amount', 'status',
            'vtu_reference', 'error_message', 'executed_at'
        ]
        read_only_fields = fields


class AutoTopUpDetailSerializer(AutoTopUpSerializer):
    history = AutoTopUpHistorySerializer(many=True, read_only=True)
    
    class Meta(AutoTopUpSerializer.Meta):
        fields = AutoTopUpSerializer.Meta.fields + ['history']