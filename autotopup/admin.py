from django.contrib import admin
from .models import AutoTopUp, AutoTopUpHistory


@admin.register(AutoTopUp)
class AutoTopUpAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'service_type', 'amount', 'phone_number',
        'is_active', 'is_locked', 'next_run', 'total_runs'
    ]
    list_filter = ['service_type', 'is_active', 'is_locked', 'network']
    search_fields = ['user__username', 'user__email', 'phone_number']
    readonly_fields = [
        'created_at', 'updated_at', 'last_run', 'total_runs',
        'failed_runs', 'is_locked', 'locked_amount'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Service Details', {
            'fields': ('service_type', 'amount', 'phone_number', 'network', 'plan')
        }),
        ('Schedule', {
            'fields': ('start_date', 'repeat_days', 'next_run', 'is_active')
        }),
        ('Wallet Lock', {
            'fields': ('is_locked', 'locked_amount')
        }),
        ('Statistics', {
            'fields': ('last_run', 'total_runs', 'failed_runs')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(AutoTopUpHistory)
class AutoTopUpHistoryAdmin(admin.ModelAdmin):
    list_display = ['auto_topup', 'amount', 'status', 'executed_at']
    list_filter = ['status', 'executed_at']
    search_fields = ['auto_topup__user__username', 'vtu_reference']
    readonly_fields = ['executed_at']
