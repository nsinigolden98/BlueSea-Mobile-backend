from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'balance_display', 'locked_balance_display',
        'available_balance_display', 'status_badge', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'user__surname', 'user__other_names']
    readonly_fields = ['created_at', 'updated_at', 'available_balance_display']
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['freeze_wallets', 'unfreeze_wallets']

    fieldsets = (
        ('Account', {'fields': ('user',)}),
        ('Balance Information', {'fields': ('balance', 'locked_balance', 'available_balance_display')}),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'

    def _format_currency(self, amount, color=None):
        if color is None:
            color = '#28a745' if amount > 0 else '#6c757d'
        formatted = f'{float(amount):,.2f}'  # pre-format before format_html
        return format_html(
            '<span style="font-weight:600; color:{}; font-family:monospace;">&#x20A6;{}</span>',
            color, formatted
        )

    def balance_display(self, obj):
        return self._format_currency(obj.balance)
    balance_display.short_description = 'Balance'

    def locked_balance_display(self, obj):
        color = '#dc3545' if obj.locked_balance > 0 else '#6c757d'
        return self._format_currency(obj.locked_balance, color)
    locked_balance_display.short_description = 'Locked'

    def available_balance_display(self, obj):
        return self._format_currency(obj.available_balance)
    available_balance_display.short_description = 'Available Balance'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#d4edda;color:#155724;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">ACTIVE</span>'
            )
        return format_html(
            '<span style="background:#f8d7da;color:#721c24;padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;">FROZEN</span>'
        )
    status_badge.short_description = 'Wallet Status'

    def freeze_wallets(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} wallet(s) frozen.', messages.WARNING)
    freeze_wallets.short_description = 'Freeze selected wallets'

    def unfreeze_wallets(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} wallet(s) unfrozen.', messages.SUCCESS)
    unfreeze_wallets.short_description = 'Unfreeze selected wallets'
