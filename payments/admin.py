from django.contrib import admin
from django.utils.html import format_html
from .models import (
    AirtimeTopUp, MTNDataTopUp, AirtelDataTopUp, GloDataTopUp, EtisalatDataTopUp,
    DSTVPayment, GOTVPayment, StartimesPayment, ShowMaxPayment,
    ElectricityPayment, WAECRegitration, WAECResultChecker, JAMBRegistration,
    Airtime2Cash, ElectricityPaymentCustomers,
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
    list_display = ['phone_number', 'network_badge', 'amount_display', 'request_id', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['phone_number', 'request_id']
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
    list_display = ['phone_number', 'plan', 'billersCode', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id', 'billersCode']
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
    list_display = ['billersCode', 'dstv_plan', 'subscription_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['subscription_type', 'created_at']
    search_fields = ['billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(GOTVPayment)
class GOTVPaymentAdmin(admin.ModelAdmin):
    list_display = ['billersCode', 'gotv_plan', 'subscription_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['subscription_type', 'created_at']
    search_fields = ['billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(StartimesPayment)
class StartimesPaymentAdmin(admin.ModelAdmin):
    list_display = ['billersCode', 'startimes_plan', 'phone_number', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(ShowMaxPayment)
class ShowMaxPaymentAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'showmax_plan', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(ElectricityPayment)
class ElectricityPaymentAdmin(admin.ModelAdmin):
    list_display = ['billerCode', 'biller_name', 'meter_type_badge', 'amount_display', 'request_id', 'created_at']
    list_filter = ['biller_name', 'meter_type', 'created_at']
    search_fields = ['billerCode', 'request_id']
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
    list_display = ['phone_number', 'request_id', 'created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(WAECResultChecker)
class WAECResultCheckerAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'request_id', 'created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(JAMBRegistration)
class JAMBRegistrationAdmin(admin.ModelAdmin):
    list_display = ['billerCode', 'exam_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['exam_type', 'created_at']
    search_fields = ['billerCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30


@admin.register(Airtime2Cash)
class Airtime2CashAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'network_badge', 'amount_display', 'request_id', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['phone_number', 'request_id']
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
    list_display = ['biller', 'meter_number', 'meter_type']
    list_filter = ['biller', 'meter_type']
    search_fields = ['meter_number']
    list_per_page = 30
