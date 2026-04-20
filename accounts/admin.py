from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.contrib import messages
from .models import Profile, EmailVerification, ResetPassword, ResetPasswordValuationToken


@admin.register(Profile)
class ProfileAdmin(UserAdmin):
    list_display = [
        'email', 'full_name', 'phone', 'role_badge',
        'email_verified_display', 'is_active_display', 'is_staff', 'created_on', 'referral_code'
    ]
    list_filter = ['role', 'email_verified', 'is_active', 'is_staff', 'created_on']
    search_fields = ['email', 'surname', 'other_names', 'phone']
    readonly_fields = ['created_on', 'profile_photo', 'referral_code']
    ordering = ['-created_on']
    list_per_page = 25
    list_display_links = ['email', 'full_name']
    actions = ['activate_users', 'deactivate_users', 'verify_emails']

    fieldsets = (
        ('Account Credentials', {'fields': ('email', 'password')}),
        ('Profile Photo', {'fields': ('profile_photo', 'image')}),
        ('Personal Information', {'fields': ('surname', 'other_names', 'phone')}),
        ('Permissions & Role', {
            'fields': ('role', 'email_verified', 'is_active', 'is_staff', 'is_admin', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('PIN Settings', {'fields': ('pin_is_set',)}),
        ('Timestamps', {'fields': ('created_on',), 'classes': ('collapse',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'surname', 'other_names', 'password1', 'password2'),
        }),
    )

    def full_name(self, obj):
        name = f"{obj.surname} {obj.other_names}".strip()
        return name if name else '—'
    full_name.short_description = 'Full Name'

    def profile_photo(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid #dee2e6;" />',
                obj.image.url
            )
        return format_html(
            '<div style="width:80px; height:80px; border-radius:50%; background:#6c757d; display:flex; '
            'align-items:center; justify-content:center; color:#fff; font-size:24px;">'
            '<i class="fas fa-user"></i></div>'
        )
    profile_photo.short_description = 'Photo'

    def role_badge(self, obj):
        colors = {
            'user': ('#17a2b8', '#fff'),
            'admin': ('#dc3545', '#fff'),
            'vendor': ('#28a745', '#fff'),
            'superuser': ('#6f42c1', '#fff'),
        }
        bg, text = colors.get(obj.role.lower(), ('#6c757d', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{}</span>',
            bg, text, obj.role
        )
    role_badge.short_description = 'Role'

    def email_verified_display(self, obj):
        if obj.email_verified:
            return format_html(
                '<span style="color:#28a745;font-weight:600;">'
                '<i class="fas fa-check-circle"></i> Verified</span>'
            )
        return format_html(
            '<span style="color:#dc3545;font-weight:600;">'
            '<i class="fas fa-times-circle"></i> Unverified</span>'
        )
    email_verified_display.short_description = 'Email Status'

    def is_active_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color:#28a745;font-weight:600;">'
                '<i class="fas fa-circle"></i> Active</span>'
            )
        return format_html(
            '<span style="color:#6c757d;font-weight:600;">'
            '<i class="fas fa-circle"></i> Inactive</span>'
        )
    is_active_display.short_description = 'Status'

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) activated successfully.', messages.SUCCESS)
    activate_users.short_description = 'Activate selected users'

    def deactivate_users(self, request, queryset):
        updated = queryset.filter(is_superuser=False).update(is_active=False)
        self.message_user(request, f'{updated} user(s) deactivated.', messages.WARNING)
    deactivate_users.short_description = 'Deactivate selected users'

    def verify_emails(self, request, queryset):
        updated = queryset.update(email_verified=True)
        self.message_user(request, f'{updated} user(s) email verified.', messages.SUCCESS)
    verify_emails.short_description = 'Mark selected users as email verified'


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'otp', 'timestamp']
    search_fields = ['email']
    readonly_fields = ['timestamp']
    list_per_page = 25


@admin.register(ResetPassword)
class ResetPasswordAdmin(admin.ModelAdmin):
    list_display = ['profile', 'otp', 'timestamp']
    search_fields = ['profile__email']
    readonly_fields = ['timestamp']
    list_per_page = 25


@admin.register(ResetPasswordValuationToken)
class ResetPasswordValuationTokenAdmin(admin.ModelAdmin):
    list_display = ['reset_token', 'created_on']
    readonly_fields = ['created_on']
    list_per_page = 25
