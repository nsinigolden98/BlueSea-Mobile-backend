from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from loyalty_market.models import Reward, RedemptionTransaction


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category', 'points_cost_display',
        'inventory_badge', 'fulfilment_type', 'availability_status', 'created_at'
    ]
    list_filter = ['category', 'fulfilment_type', 'created_at']
    search_fields = ['title', 'description', 'category']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25

    fieldsets = (
        ('Basic Information', {'fields': ('id', 'user', 'title', 'description', 'category')}),
        ('Reward Details', {'fields': ('image_url', 'points_cost', 'inventory', 'polarity_score')}),
        ('Availability', {'fields': ('availability_start', 'availability_end')}),
        ('Fulfilment', {'fields': ('fulfilment_type',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def points_cost_display(self, obj):
        return format_html(
            '<span style="font-weight:700;color:#6f42c1;">{} pts</span>',
            f'{obj.points_cost:,}'
        )
    points_cost_display.short_description = 'Points Cost'

    def inventory_badge(self, obj):
        count = obj.inventory
        if count is None:
            return format_html('<span style="color:#6c757d;">Unlimited</span>')
        if count <= 0:
            return format_html(
                '<span style="background:#f8d7da;color:#721c24;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">OUT OF STOCK</span>'
            )
        elif count < 10:
            return format_html(
                '<span style="background:#fff3cd;color:#856404;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">LOW ({} left)</span>',
                count
            )
        return format_html(
            '<span style="background:#d4edda;color:#155724;padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;">IN STOCK ({})</span>',
            count
        )
    inventory_badge.short_description = 'Inventory'

    def availability_status(self, obj):
        now = timezone.now()
        if obj.availability_start and now < obj.availability_start:
            return format_html('<span style="color:#ffc107;font-weight:600;">Upcoming</span>')
        if obj.availability_end and now > obj.availability_end:
            return format_html('<span style="color:#6c757d;">Expired</span>')
        return format_html('<span style="color:#28a745;font-weight:600;">Available</span>')
    availability_status.short_description = 'Availability'


@admin.register(RedemptionTransaction)
class RedemptionTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_link', 'reward_link',
        'points_deducted_display', 'status_badge', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'redeemed_at']
    search_fields = ['user_id__email', 'reward_id__title']
    readonly_fields = ['id', 'created_at', 'redeemed_at']
    list_per_page = 25
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Transaction Details', {'fields': ('id', 'user_id', 'reward_id', 'points_deducted', 'status')}),
        ('Fulfilment', {'fields': ('fulfilment_payload',)}),
        ('Timestamps', {'fields': ('created_at', 'redeemed_at'), 'classes': ('collapse',)}),
    )

    def user_link(self, obj):
        url = reverse('admin:accounts_profile_change', args=[obj.user_id.id])
        return format_html('<a href="{}">{}</a>', url, obj.user_id.email)
    user_link.short_description = 'User'

    def reward_link(self, obj):
        url = reverse('admin:loyalty_market_reward_change', args=[obj.reward_id.id])
        return format_html('<a href="{}">{}</a>', url, obj.reward_id.title)
    reward_link.short_description = 'Reward'

    def points_deducted_display(self, obj):
        return format_html(
            '<span style="font-weight:700;color:#dc3545;">−{} pts</span>',
            f'{obj.points_deducted:,}'
        )
    points_deducted_display.short_description = 'Points Used'

    def status_badge(self, obj):
        colors = {
            'pending': ('#fff3cd', '#856404'),
            'completed': ('#d4edda', '#155724'),
            'failed': ('#f8d7da', '#721c24'),
            'cancelled': ('#e2e3e5', '#383d41'),
        }
        bg, text = colors.get(str(obj.status).lower(), ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.status
        )
    status_badge.short_description = 'Status'
