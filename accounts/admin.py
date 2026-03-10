from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Profile, EmailVerification, ResetPassword, ResetPasswordValuationToken


@admin.register(Profile)
class ProfileAdmin(UserAdmin):
    list_display = ['email', 'surname', 'other_names', 'phone', 'role', 'email_verified', 'is_active', 'is_staff', 'created_on']
    list_filter = ['role', 'email_verified', 'is_active', 'is_staff', 'created_on']
    search_fields = ['email', 'surname', 'other_names', 'phone']
    readonly_fields = ['created_on']
    ordering = ['-created_on']

    fieldsets = (
        ('Account', {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('surname', 'other_names', 'phone', 'image')}),
        ('Permissions', {'fields': ('role', 'email_verified', 'is_active', 'is_staff', 'is_admin', 'is_superuser', 'groups', 'user_permissions')}),
        ('PIN', {'fields': ('pin_is_set',)}),
        ('Timestamps', {'fields': ('created_on',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'surname', 'other_names', 'password1', 'password2'),
        }),
    )


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'otp', 'timestamp']
    search_fields = ['email']
    readonly_fields = ['timestamp']


@admin.register(ResetPassword)
class ResetPasswordAdmin(admin.ModelAdmin):
    list_display = ['profile', 'otp', 'timestamp']
    search_fields = ['profile__email']
    readonly_fields = ['timestamp']


@admin.register(ResetPasswordValuationToken)
class ResetPasswordValuationTokenAdmin(admin.ModelAdmin):
    list_display = ['reset_token', 'created_on']
    readonly_fields = ['created_on']
