from django.contrib import admin
from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'locked_balance', 'available_balance', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'user__surname']
    readonly_fields = ['created_at', 'updated_at', 'available_balance']

    def available_balance(self, obj):
        return obj.available_balance
    available_balance.short_description = 'Available Balance'
