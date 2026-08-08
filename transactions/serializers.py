from rest_framework import serializers
from .models import WalletTransaction, FundWallet, AccountName, Withdraw
from decimal import Decimal
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field


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
    
    @extend_schema_field(OpenApiTypes.STR)
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
        

class WithdrawSerializer(serializers.ModelSerializer):
     
    class Meta:
        model = Withdraw
        fields =[
            "id", "amount", "account_name", "account_number","bank_name", 'bank_code', 'payment_reference','status', 'created_at', 
        ]
        read_only_fields = ['id', 'payment_reference','created_at' ]

class AccountNameSerializer(serializers.ModelSerializer):
    class Meta: 
        model = AccountName
        fields = ['id', 'account_number', 'bank_code']
        read_only_fields =['id']


class InitializeFundingSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("100.00"),
        help_text="Amount to fund the wallet in NGN (minimum ₦100)",
    )


class WithdrawRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    account_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=10)
    bank_name = serializers.CharField(max_length=50)
    bank_code = serializers.CharField(max_length=10)
    transaction_pin = serializers.CharField(write_only=True, max_length=6, help_text="6-digit transaction PIN")