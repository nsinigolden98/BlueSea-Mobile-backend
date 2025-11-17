from rest_framework import serializers
from .models import WalletTransaction, FundWallet


class WalletTransactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='wallet.user.username', read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'transaction_type', 'amount', 'formatted_amount', 
            'description', 'reference', 'status', 'created_at', 'username'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_formatted_amount(self, obj):
        return f"₦{obj.amount:,.2f}"


class WalletFundingSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = FundWallet
        fields = [
            'id', 'amount', 'formatted_amount', 'payment_method', 
            'payment_reference', 'status', 'created_at', 'username'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_formatted_amount(self, obj):
        return f"₦{obj.amount:,.2f}"
        