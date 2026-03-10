from django.contrib import admin
from .models import Group, GroupMember


class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0
    fields = ['user', 'role', 'joined_at']
    readonly_fields = ['joined_at']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'service_type', 'target_amount', 'active', 'created_at']
    list_filter = ['service_type', 'active', 'created_at']
    search_fields = ['name', 'created_by__email', 'join_code', 'sub_number']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [GroupMemberInline]


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__email', 'group__name']
    readonly_fields = ['joined_at']
