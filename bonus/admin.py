from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from .models import BonusPoint, BonusHistory, BonusCampaign, Referral
from .utils import award_points


@admin.register(BonusPoint)
class BonusPointAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'points_display', 'lifetime_earned',
        'lifetime_redeemed', 'last_daily_login', 'created_at'
    ]
    list_filter = ['created_at', 'last_daily_login']
    search_fields = ['user__email', 'user__surname', 'user__other_names']
    readonly_fields = ['lifetime_earned', 'lifetime_redeemed', 'created_at', 'updated_at']
    actions = ['add_bonus_points', 'deduct_points', 'reset_points']
    list_per_page = 25

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'

    def points_display(self, obj):
        color = '#28a745' if obj.points > 0 else '#6c757d'
        return format_html(
            '<span style="font-weight:700;color:{};font-size:13px;">{} pts</span>',
            color, f'{obj.points:,}'
        )
    points_display.short_description = 'Current Points'

    def add_bonus_points(self, request, queryset):
        for bonus_account in queryset:
            try:
                award_points(
                    user=bonus_account.user,
                    points=100,
                    reason='admin_award',
                    description=f'Admin bonus by {request.user.email}',
                    created_by=request.user
                )
                self.message_user(request, f'Added 100 pts to {bonus_account.user.email}', messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f'Error for {bonus_account.user.email}: {e}', messages.ERROR)
    add_bonus_points.short_description = 'Add 100 bonus points to selected users'

    def deduct_points(self, request, queryset):
        for bonus_account in queryset:
            try:
                if bonus_account.points >= 50:
                    balance_before = bonus_account.points
                    bonus_account.deduct_points(50)
                    BonusHistory.objects.create(
                        user=bonus_account.user,
                        transaction_type='adjusted',
                        points=-50,
                        reason='admin_award',
                        description=f'Admin deduction by {request.user.email}',
                        balance_before=balance_before,
                        balance_after=bonus_account.points,
                        created_by=request.user
                    )
                    self.message_user(request, f'Deducted 50 pts from {bonus_account.user.email}', messages.SUCCESS)
                else:
                    self.message_user(
                        request, f'{bonus_account.user.email} has insufficient points', messages.WARNING
                    )
            except Exception as e:
                self.message_user(request, f'Error for {bonus_account.user.email}: {e}', messages.ERROR)
    deduct_points.short_description = 'Deduct 50 points from selected users'

    def reset_points(self, request, queryset):
        for bonus_account in queryset:
            balance_before = bonus_account.points
            bonus_account.points = 0
            bonus_account.save()
            BonusHistory.objects.create(
                user=bonus_account.user,
                transaction_type='adjusted',
                points=-balance_before,
                reason='admin_award',
                description=f'Points reset by {request.user.email}',
                balance_before=balance_before,
                balance_after=0,
                created_by=request.user
            )
        self.message_user(request, f'Reset points for {queryset.count()} user(s).', messages.SUCCESS)
    reset_points.short_description = 'Reset points to zero for selected users'


@admin.register(BonusHistory)
class BonusHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'transaction_type_display', 'points_display',
        'reason', 'balance_after', 'created_at'
    ]
    list_filter = ['transaction_type', 'reason', 'created_at']
    search_fields = ['user__email', 'description', 'reference']
    readonly_fields = [
        'user', 'transaction_type', 'points', 'reason', 'description',
        'reference', 'balance_before', 'balance_after', 'created_at', 'created_by', 'metadata'
    ]
    date_hierarchy = 'created_at'
    list_per_page = 30

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'

    def transaction_type_display(self, obj):
        colors = {
            'earned': ('#d4edda', '#155724'),
            'redeemed': ('#f8d7da', '#721c24'),
            'adjusted': ('#fff3cd', '#856404'),
            'expired': ('#e2e3e5', '#383d41'),
            'reversed': ('#d1ecf1', '#0c5460'),
        }
        bg, text = colors.get(obj.transaction_type, ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.get_transaction_type_display()
        )
    transaction_type_display.short_description = 'Type'

    def points_display(self, obj):
        color = '#28a745' if obj.points > 0 else '#dc3545'
        sign = '+' if obj.points > 0 else ''
        return format_html(
            '<span style="font-weight:700;color:{};font-size:13px;">{}{}</span>',
            color, sign, obj.points
        )
    points_display.short_description = 'Points'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BonusCampaign)
class BonusCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_type', 'status_display', 'multiplier', 'start_date', 'end_date']
    list_filter = ['is_active', 'campaign_type', 'start_date']
    search_fields = ['name', 'description']
    date_hierarchy = 'start_date'
    list_per_page = 25

    fieldsets = (
        ('Campaign Information', {'fields': ('name', 'description', 'campaign_type')}),
        ('Settings', {'fields': ('multiplier', 'bonus_amount', 'is_active')}),
        ('Duration', {'fields': ('start_date', 'end_date')}),
    )

    def status_display(self, obj):
        if obj.is_running():
            return format_html(
                '<span style="background:#d4edda;color:#155724;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">RUNNING</span>'
            )
        elif obj.is_active and obj.start_date > timezone.now():
            return format_html(
                '<span style="background:#fff3cd;color:#856404;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">SCHEDULED</span>'
            )
        elif obj.end_date < timezone.now():
            return format_html(
                '<span style="background:#e2e3e5;color:#383d41;padding:3px 10px;border-radius:12px;'
                'font-size:11px;font-weight:600;">ENDED</span>'
            )
        return format_html(
            '<span style="background:#f8d7da;color:#721c24;padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;">INACTIVE</span>'
        )
    status_display.short_description = 'Status'


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = [
        'referrer_email', 'referred_user_email', 'referral_code',
        'status_display', 'bonus_awarded', 'first_transaction_completed', 'created_at'
    ]
    list_filter = ['status', 'bonus_awarded', 'first_transaction_completed', 'created_at']
    search_fields = ['referrer__email', 'referred_user__email', 'referral_code']
    readonly_fields = ['referral_code', 'created_at', 'completed_at']
    list_per_page = 25

    def referrer_email(self, obj):
        return obj.referrer.email
    referrer_email.short_description = 'Referrer'

    def referred_user_email(self, obj):
        return obj.referred_user.email
    referred_user_email.short_description = 'Referred User'

    def status_display(self, obj):
        colors = {
            'pending': ('#fff3cd', '#856404'),
            'completed': ('#d4edda', '#155724'),
            'expired': ('#e2e3e5', '#383d41'),
        }
        bg, text = colors.get(obj.status, ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.get_status_display()
        )
    status_display.short_description = 'Status'