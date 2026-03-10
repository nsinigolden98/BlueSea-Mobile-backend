from django.contrib import admin
from .models import WalletTransaction, FundWallet, Withdraw, AccountName


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'transaction_type', 'amount', 'status', 'reference', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['wallet__user__email', 'reference', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(FundWallet)
class FundWalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'payment_reference', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email', 'payment_reference', 'gateway_reference']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(Withdraw)
class WithdrawAdmin(admin.ModelAdmin):
    list_display = ['account_name', 'bank_name', 'account_number', 'amount', 'status', 'payment_reference', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['account_name', 'account_number', 'payment_reference', 'bank_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(AccountName)
class AccountNameAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'bank_code']
    search_fields = ['account_number', 'bank_code']
