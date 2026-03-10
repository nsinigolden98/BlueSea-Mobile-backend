from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import AutoTopUp, AutoTopUpHistory


@admin.register(AutoTopUp)
class AutoTopUpAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'service_type_badge', 'amount_display', 'phone_number',
        'status_badge', 'success_rate', 'next_run_display', 'total_runs'
    ]
    list_filter = ['service_type', 'is_active', 'is_locked', 'network']
    search_fields = ['user__email', 'phone_number']
    readonly_fields = [
        'created_at', 'updated_at', 'last_run', 'total_runs',
        'failed_runs', 'is_locked', 'locked_amount'
    ]
    list_per_page = 25

    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Service Details', {'fields': ('service_type', 'amount', 'phone_number', 'network', 'plan')}),
        ('Schedule', {'fields': ('start_date', 'repeat_days', 'next_run', 'is_active')}),
        ('Wallet Lock', {'fields': ('is_locked', 'locked_amount')}),
        ('Statistics', {'fields': ('last_run', 'total_runs', 'failed_runs')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def service_type_badge(self, obj):
        colors = {
            'airtime': ('#cce5ff', '#004085'),
            'data': ('#d4edda', '#155724'),
        }
        bg, text = colors.get(str(obj.service_type).lower(), ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.service_type
        )
    service_type_badge.short_description = 'Service'

    def amount_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-weight:600;">&#x20A6;{}</span>',
            f'{float(obj.amount):,.2f}'
        )
    amount_display.short_description = 'Amount'

    def status_badge(self, obj):
        if obj.is_locked:
            return format_html(
                '<span style="background:#f8d7da;color:#721c24;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">LOCKED</span>'
            )
        if obj.is_active:
            return format_html(
                '<span style="background:#d4edda;color:#155724;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">ACTIVE</span>'
            )
        return format_html(
            '<span style="background:#e2e3e5;color:#383d41;padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;">PAUSED</span>'
        )
    status_badge.short_description = 'Status'

    def success_rate(self, obj):
        total = obj.total_runs or 0
        failed = obj.failed_runs or 0
        if total == 0:
            return format_html('<span style="color:#6c757d;">No runs yet</span>')
        success = total - failed
        rate = int((success / total) * 100)
        color = '#28a745' if rate >= 80 else ('#ffc107' if rate >= 50 else '#dc3545')
        return format_html(
            '<span style="font-weight:600;color:{};">{}%</span>',
            color, rate
        )
    success_rate.short_description = 'Success Rate'

    def next_run_display(self, obj):
        if not obj.next_run:
            return '—'
        now = timezone.now()
        diff = obj.next_run - now
        days = diff.days
        if days < 0:
            return format_html('<span style="color:#6c757d;">Overdue</span>')
        elif days == 0:
            return format_html('<span style="color:#fd7e14;font-weight:600;">Today</span>')
        elif days == 1:
            return format_html('<span style="color:#ffc107;font-weight:600;">Tomorrow</span>')
        return format_html('<span>In {} days</span>', days)
    next_run_display.short_description = 'Next Run'


@admin.register(AutoTopUpHistory)
class AutoTopUpHistoryAdmin(admin.ModelAdmin):
    list_display = ['auto_topup', 'amount_display', 'status_badge', 'executed_at']
    list_filter = ['status', 'executed_at']
    search_fields = ['auto_topup__user__email', 'vtu_reference']
    readonly_fields = ['executed_at']
    date_hierarchy = 'executed_at'
    list_per_page = 30

    def amount_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-weight:600;">&#x20A6;{}</span>',
            f'{float(obj.amount):,.2f}'
        )
    amount_display.short_description = 'Amount'

    def status_badge(self, obj):
        colors = {
            'success': ('#d4edda', '#155724'),
            'failed': ('#f8d7da', '#721c24'),
            'pending': ('#fff3cd', '#856404'),
        }
        bg, text = colors.get(str(obj.status).lower(), ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.status
        )
    status_badge.short_description = 'Status'
