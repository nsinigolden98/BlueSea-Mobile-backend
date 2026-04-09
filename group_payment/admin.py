from django.contrib import admin
from django.utils.html import format_html
from .models import Group, GroupMember


class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0
    fields = ['user', 'role', 'joined_at']
    readonly_fields = ['joined_at']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'created_by', 'service_type_badge',
        'member_count', 'target_amount_display', 'status_badge', 'created_at'
    ]
    list_filter = ['service_type', 'active', 'created_at']
    search_fields = ['name', 'created_by__email', 'join_code', 'sub_number']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [GroupMemberInline]
    list_per_page = 25

    def service_type_badge(self, obj):
        colors = {
            'airtime': ('#cce5ff', '#004085'),
            'data': ('#d4edda', '#155724'),
            'electricity': ('#fff3cd', '#856404'),
            'cable': ('#d1ecf1', '#0c5460'),
        }
        key = str(obj.service_type).lower()
        bg, text = colors.get(key, ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.service_type
        )
    service_type_badge.short_description = 'Service'

    def member_count(self, obj):
        count = len(obj.invite_members.split(','))
        return format_html(
            '<span style="font-weight:600;">{} member{}</span>',
            count, 's' if count != 1 else ''
        )
    member_count.short_description = 'Members'

    def target_amount_display(self, obj):
        if obj.target_amount:
            return format_html(
                '<span style="font-family:monospace;font-weight:600;">&#x20A6;{}</span>',
                f'{float(obj.target_amount):,.2f}'
            )
        return '—'
    target_amount_display.short_description = 'Target Amount'

    def status_badge(self, obj):
        if obj.active:
            return format_html(
                '<span style="background:#d4edda;color:#155724;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">ACTIVE</span>'
            )
        return format_html(
            '<span style="background:#e2e3e5;color:#383d41;padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;">INACTIVE</span>'
        )
    status_badge.short_description = 'Status'


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'role_badge', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__email', 'group__name']
    readonly_fields = ['joined_at']
    list_per_page = 25

    def role_badge(self, obj):
        colors = {
            'admin': ('#f8d7da', '#721c24'),
            'member': ('#d1ecf1', '#0c5460'),
            'owner': ('#d4edda', '#155724'),
        }
        bg, text = colors.get(str(obj.role).lower(), ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.role
        )
    role_badge.short_description = 'Role'
