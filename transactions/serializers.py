from rest_framework import serializers
from .models import WalletTransaction, FundWallet, AccountName, Withdraw


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
        

class WithdrawSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdraw
        fields =[
            "id", "amount", "account_number", 'bank_code', 'payment_reference', 'status', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at']

class AccountNameSerializer(serializers.ModelSerializer):
    class Meta: 
        model = AccountName
        fields = ['id', 'account_number', 'bank_code']
        read_only_fields =['id']