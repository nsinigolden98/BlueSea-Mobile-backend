from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    AirtimeTopUp, MTNDataTopUp, AirtelDataTopUp, GloDataTopUp, EtisalatDataTopUp,
    DSTVPayment, GOTVPayment, StartimesPayment, ShowMaxPayment,
    ElectricityPayment, WAECRegitration, WAECResultChecker, JAMBRegistration,
    Airtime2Cash, ElectricityPaymentCustomers, Withdrawal,
)


def _network_badge(network):
    palette = {
        'mtn': ('#ffc107', '#000'),
        'airtel': ('#dc3545', '#fff'),
        'glo': ('#28a745', '#fff'),
        'etisalat': ('#17a2b8', '#fff'),
        '9mobile': ('#17a2b8', '#fff'),
    }
    bg, text = palette.get(str(network).lower(), ('#6c757d', '#fff'))
    return format_html(
        '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
        'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
        bg, text, network
    )


def _fmt(amount):
    """Pre-format a Decimal/float as a currency string for use inside format_html."""
    return f'{float(amount):,.2f}'


@admin.register(AirtimeTopUp)
class AirtimeTopUpAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'network_badge', 'amount_display', 'request_id', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['user__email', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30

    def network_badge(self, obj):
        return _network_badge(obj.network)
    network_badge.short_description = 'Network'

    def amount_display(self, obj):
        return format_html(
            '<span style="font-weight:600;color:#343a40;font-family:monospace;">&#x20A6;{}</span>',
            _fmt(obj.amount)
        )
    amount_display.short_description = 'Amount'


class DataTopUpBase(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'plan', 'billersCode', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'phone_number', 'request_id', 'billersCode']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(MTNDataTopUp)
class MTNDataTopUpAdmin(DataTopUpBase):
    pass


@admin.register(AirtelDataTopUp)
class AirtelDataTopUpAdmin(DataTopUpBase):
    pass


@admin.register(GloDataTopUp)
class GloDataTopUpAdmin(DataTopUpBase):
    pass


@admin.register(EtisalatDataTopUp)
class EtisalatDataTopUpAdmin(DataTopUpBase):
    pass


@admin.register(DSTVPayment)
class DSTVPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'billersCode', 'dstv_plan', 'subscription_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['subscription_type', 'created_at']
    search_fields = ['user__email', 'billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(GOTVPayment)
class GOTVPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'billersCode', 'gotv_plan', 'subscription_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['subscription_type', 'created_at']
    search_fields = ['user__email', 'billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(StartimesPayment)
class StartimesPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'billersCode', 'startimes_plan', 'phone_number', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(ShowMaxPayment)
class ShowMaxPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'showmax_plan', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(ElectricityPayment)
class ElectricityPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'billerCode', 'biller_name', 'meter_type_badge', 'amount_display', 'request_id', 'created_at']
    list_filter = ['biller_name', 'meter_type', 'created_at']
    search_fields = ['user__email', 'billerCode', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30

    def meter_type_badge(self, obj):
        colors = {
            'prepaid': ('#28a745', '#fff'),
            'postpaid': ('#17a2b8', '#fff'),
        }
        bg, text = colors.get(str(obj.meter_type).lower(), ('#6c757d', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:600;">{}</span>',
            bg, text, obj.meter_type
        )
    meter_type_badge.short_description = 'Meter Type'

    def amount_display(self, obj):
        return format_html(
            '<span style="font-weight:600;font-family:monospace;">&#x20A6;{}</span>',
            _fmt(obj.amount)
        )
    amount_display.short_description = 'Amount'


@admin.register(WAECRegitration)
class WAECRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'request_id', 'created_at']
    search_fields = ['user__email', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(WAECResultChecker)
class WAECResultCheckerAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'request_id', 'created_at']
    search_fields = ['user__email', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(JAMBRegistration)
class JAMBRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'billerCode', 'exam_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['exam_type', 'created_at']
    search_fields = ['user__email', 'billerCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(Airtime2Cash)
class Airtime2CashAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'network_badge', 'amount_display', 'request_id', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['user__email', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30

    def network_badge(self, obj):
        return _network_badge(obj.network)
    network_badge.short_description = 'Network'

    def amount_display(self, obj):
        return format_html(
            '<span style="font-weight:600;font-family:monospace;">&#x20A6;{}</span>',
            _fmt(obj.amount)
        )
    amount_display.short_description = 'Amount'


@admin.register(ElectricityPaymentCustomers)
class ElectricityPaymentCustomersAdmin(admin.ModelAdmin):
    list_display = ['user', 'biller', 'meter_number', 'meter_type']
    list_filter = ['biller', 'meter_type']
    search_fields = ['user__email', 'meter_number']
    list_per_page = 30

def _status_badge(status):
    palette = {
        'pending': ('#ffc107', '#000'),
        'successful': ('#28a745', '#fff'),
        'failed': ('#dc3545', '#fff'),
    }
    bg, text = palette.get(str(status).lower(), ('#6c757d', '#fff'))
    return format_html(
        '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
        'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
        bg, text, status
    )


def _notify_withdrawal(user, title, message, email_subject):
    from notifications.utils import send_notification
    send_notification(
        user=user,
        title=title,
        message=message,
        notification_type='payment',
        email_subject=email_subject,
    )


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount_display', 'status_display', 'account_number', 'bank_code', 'bank_name', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['account_name', 'account_number', 'payment_reference', 'user__email']
    readonly_fields = ['user', 'payment_reference', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'
    list_per_page = 30
    actions = ['mark_successful', 'mark_failed']

    def amount_display(self, obj):
        return format_html(
            '<span style="font-weight:600;font-family:monospace;">&#x20A6;{}</span>',
            _fmt(obj.amount)
        )
    amount_display.short_description = 'Amount'

    def status_display(self, obj):
        return _status_badge(obj.status)
    status_display.short_description = 'Status'

    def mark_successful(self, request, queryset):
        pending = queryset.filter(status='pending')
        updated = pending.update(status='successful', completed_at=timezone.now())
        for withdrawal in pending:
            try:
                _notify_withdrawal(
                    withdrawal.user,
                    'Withdrawal Completed',
                    f'Your withdrawal of ₦{withdrawal.amount} to '
                    f'{withdrawal.account_name} ({withdrawal.account_number}) was successful.',
                    'BlueSea - Withdrawal Completed',
                )
            except Exception as e:
                self.message_user(request, f'Notification failed: {e}', level=messages.ERROR)
        self.message_user(
            request,
            f'{updated} withdrawal(s) marked as successful.',
            level=messages.SUCCESS,
        )
    mark_successful.short_description = 'Mark selected withdrawals as successful'

    def mark_failed(self, request, queryset):
        pending = queryset.filter(status='pending')
        refunded = 0
        for withdrawal in pending:
            try:
                with transaction.atomic():
                    withdrawal.completed_at = timezone.now()
                    withdrawal.status = 'failed'
                    withdrawal.save(update_fields=['status', 'completed_at'])
                    withdrawal.user.wallet.credit(
                        amount=withdrawal.amount,
                        description=f'Refund for failed withdrawal {withdrawal.payment_reference}',
                        reference=withdrawal.payment_reference,
                    )
                    refunded += 1
                    try:
                        _notify_withdrawal(
                            withdrawal.user,
                            'Withdrawal Failed',
                            f'Your withdrawal of ₦{withdrawal.amount} to '
                            f'{withdrawal.account_name} ({withdrawal.account_number}) failed '
                            'and has been refunded to your wallet.',
                            'BlueSea - Withdrawal Failed',
                        )
                    except Exception as e:
                        self.message_user(request, f'Notification failed: {e}', level=messages.ERROR)
            except Exception as e:
                self.message_user(
                    request,
                    f'Could not mark withdrawal {withdrawal.id} failed: {e}',
                    level=messages.ERROR,
                )
        self.message_user(
            request,
            f'{refunded} withdrawal(s) marked as failed and refunded.',
            level=messages.SUCCESS,
        )
    mark_failed.short_description = 'Mark selected withdrawals as failed (refunds wallet)'
