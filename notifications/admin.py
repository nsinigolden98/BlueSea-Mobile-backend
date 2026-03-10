from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import Notification


NOTIFICATION_ICONS = {
    'payment': 'fas fa-credit-card',
    'bonus': 'fas fa-coins',
    'promo': 'fas fa-bullhorn',
    'event': 'fas fa-calendar-alt',
    'transfer': 'fas fa-exchange-alt',
    'alert': 'fas fa-exclamation-circle',
    'general': 'fas fa-bell',
}


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'type_badge', 'title_truncated',
        'read_status', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']
    list_per_page = 30

    def type_badge(self, obj):
        colors = {
            'payment': ('#d1ecf1', '#0c5460'),
            'bonus': ('#fff3cd', '#856404'),
            'promo': ('#d4edda', '#155724'),
            'event': ('#e2d9f3', '#4a235a'),
            'transfer': ('#cce5ff', '#004085'),
            'alert': ('#f8d7da', '#721c24'),
            'general': ('#e2e3e5', '#383d41'),
        }
        key = getattr(obj, 'notification_type', 'general').lower()
        bg, text = colors.get(key, ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.notification_type
        )
    type_badge.short_description = 'Type'

    def title_truncated(self, obj):
        title = obj.title or ''
        if len(title) > 60:
            return f'{title[:60]}...'
        return title
    title_truncated.short_description = 'Title'

    def read_status(self, obj):
        if obj.is_read:
            return format_html(
                '<span style="color:#28a745;font-weight:600;">Read</span>'
            )
        return format_html(
            '<span style="color:#dc3545;font-weight:600;">Unread</span>'
        )
    read_status.short_description = 'Read Status'

    def mark_as_read(self, request, queryset):
        updated = queryset.filter(is_read=False).update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marked as read.', messages.SUCCESS)
    mark_as_read.short_description = 'Mark selected notifications as read'

    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(is_read=True).update(is_read=False)
        self.message_user(request, f'{updated} notification(s) marked as unread.', messages.INFO)
    mark_as_unread.short_description = 'Mark selected notifications as unread'
