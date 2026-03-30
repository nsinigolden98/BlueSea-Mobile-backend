from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import WalletTransaction, FundWallet, Withdraw, AccountName


def _status_badge(status):
    """Reusable status badge renderer."""
    palettes = {
        'success': ('#d4edda', '#155724'),
        'successful': ('#d4edda', '#155724'),
        'completed': ('#d4edda', '#155724'),
        'pending': ('#fff3cd', '#856404'),
        'processing': ('#fff3cd', '#856404'),
        'failed': ('#f8d7da', '#721c24'),
        'reversed': ('#d1ecf1', '#0c5460'),
        'refunded': ('#d1ecf1', '#0c5460'),
    }
    bg, color = palettes.get(status.lower(), ('#e2e3e5', '#383d41'))
    return format_html(
        '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
        'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
        bg, color, status
    )


def _amount_display(amount, tx_type=None):
    """Format amounts with sign and currency symbol."""
    debit_types = {'debit', 'withdrawal', 'payment', 'transfer_out'}
    is_debit = tx_type and tx_type.lower() in debit_types
    color = '#dc3545' if is_debit else '#28a745'
    sign = '−' if is_debit else '+'
    formatted = f'{float(amount):,.2f}'  # pre-format before format_html
    return format_html(
        '<span style="font-weight:600;color:{};font-family:monospace;">{} &#x20A6;{}</span>',
        color, sign, formatted
    )


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'wallet_user', 'transaction_type_badge', 'amount_display',
        'status_display', 'reference', 'created_at'
    ]
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['wallet__user__email', 'reference', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30

    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'

    def transaction_type_badge(self, obj):
        colors = {
            'credit': ('#28a745', '#fff'),
            'debit': ('#dc3545', '#fff'),
            'transfer_in': ('#17a2b8', '#fff'),
            'transfer_out': ('#fd7e14', '#fff'),
        }
        bg, text = colors.get(obj.transaction_type.lower(), ('#6c757d', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.transaction_type
        )
    transaction_type_badge.short_description = 'Type'

    def amount_display(self, obj):
        return _amount_display(obj.amount, obj.transaction_type)
    amount_display.short_description = 'Amount'

    def status_display(self, obj):
        return _status_badge(obj.status)
    status_display.short_description = 'Status'


@admin.register(FundWallet)
class FundWalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'amount_display', 'status_display',
        'payment_reference', 'created_at', 'completed_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__email', 'payment_reference', 'gateway_reference']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30

    def amount_display(self, obj):
        formatted = f'{float(obj.amount):,.2f}'
        return format_html(
            '<span style="font-weight:600;color:#28a745;font-family:monospace;">+ &#x20A6;{}</span>',
            formatted
        )
    amount_display.short_description = 'Amount'

    def status_display(self, obj):
        return _status_badge(obj.status)
    status_display.short_description = 'Status'


@admin.register(Withdraw)
class WithdrawAdmin(admin.ModelAdmin):
    list_display = [
        'account_name', 'bank_name', 'account_number',
        'amount_display', 'status_display', 'payment_reference', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['account_name', 'account_number', 'payment_reference', 'bank_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30

    def amount_display(self, obj):
        formatted = f'{float(obj.amount):,.2f}'
        return format_html(
            '<span style="font-weight:600;color:#dc3545;font-family:monospace;">− &#x20A6;{}</span>',
            formatted
        )
    amount_display.short_description = 'Amount'

    def status_display(self, obj):
        return _status_badge(obj.status)
    status_display.short_description = 'Status'


@admin.register(AccountName)
class AccountNameAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'bank_code']
    search_fields = ['account_number', 'bank_code']
    list_per_page = 25
