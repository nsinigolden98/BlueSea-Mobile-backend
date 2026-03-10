from django.contrib import admin
from .models import (
    AirtimeTopUp, MTNDataTopUp, AirtelDataTopUp, GloDataTopUp, EtisalatDataTopUp,
    DSTVPayment, GOTVPayment, StartimesPayment, ShowMaxPayment,
    ElectricityPayment, WAECRegitration, WAECResultChecker, JAMBRegistration,
    Airtime2Cash, ElectricityPaymentCustomers,
)


@admin.register(AirtimeTopUp)
class AirtimeTopUpAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'network', 'amount', 'request_id', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(MTNDataTopUp)
class MTNDataTopUpAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'plan', 'billersCode', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id', 'billersCode']
    readonly_fields = ['created_at']


@admin.register(AirtelDataTopUp)
class AirtelDataTopUpAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'plan', 'billersCode', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id', 'billersCode']
    readonly_fields = ['created_at']


@admin.register(GloDataTopUp)
class GloDataTopUpAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'plan', 'billersCode', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id', 'billersCode']
    readonly_fields = ['created_at']


@admin.register(EtisalatDataTopUp)
class EtisalatDataTopUpAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'plan', 'billersCode', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id', 'billersCode']
    readonly_fields = ['created_at']


@admin.register(DSTVPayment)
class DSTVPaymentAdmin(admin.ModelAdmin):
    list_display = ['billersCode', 'dstv_plan', 'subscription_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['subscription_type', 'created_at']
    search_fields = ['billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(GOTVPayment)
class GOTVPaymentAdmin(admin.ModelAdmin):
    list_display = ['billersCode', 'gotv_plan', 'subscription_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['subscription_type', 'created_at']
    search_fields = ['billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(StartimesPayment)
class StartimesPaymentAdmin(admin.ModelAdmin):
    list_display = ['billersCode', 'startimes_plan', 'phone_number', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['billersCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(ShowMaxPayment)
class ShowMaxPaymentAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'showmax_plan', 'request_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(ElectricityPayment)
class ElectricityPaymentAdmin(admin.ModelAdmin):
    list_display = ['billerCode', 'biller_name', 'meter_type', 'amount', 'request_id', 'created_at']
    list_filter = ['biller_name', 'meter_type', 'created_at']
    search_fields = ['billerCode', 'request_id']
    readonly_fields = ['created_at']


@admin.register(WAECRegitration)
class WAECRegistrationAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'request_id', 'created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(WAECResultChecker)
class WAECResultCheckerAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'request_id', 'created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(JAMBRegistration)
class JAMBRegistrationAdmin(admin.ModelAdmin):
    list_display = ['billerCode', 'exam_type', 'phone_number', 'request_id', 'created_at']
    list_filter = ['exam_type', 'created_at']
    search_fields = ['billerCode', 'phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(Airtime2Cash)
class Airtime2CashAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'network', 'amount', 'request_id', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['phone_number', 'request_id']
    readonly_fields = ['created_at']


@admin.register(ElectricityPaymentCustomers)
class ElectricityPaymentCustomersAdmin(admin.ModelAdmin):
    list_display = ['biller', 'meter_number', 'meter_type']
    list_filter = ['biller', 'meter_type']
    search_fields = ['meter_number']
