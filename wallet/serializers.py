from rest_framework import serializers
from .models import Wallet

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['id', 'user', 'balance', 'created_at', 'updated_at', 'is_active']
        read_only_fields = ['balance', 'created_at', 'updated_at']


class WalletBalanceSerializer(serializers.Serializer):
    balance = serializers.CharField(help_text="Formatted wallet balance")
    raw_balance = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Raw balance value")
    available_balance = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Available balance after locked funds")
    locked_balance = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Locked balance")