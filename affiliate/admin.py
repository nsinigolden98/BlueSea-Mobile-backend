from django.contrib import admin

from .models import AffiliateLink, AffiliateProfile, AffiliateSale


@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = [
        "affiliate_name",
        "user",
        "status",
        "commission_rate",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["affiliate_name", "user__email"]
    actions = ["approve_selected", "reject_selected"]

    @admin.action(description="Approve selected affiliates")
    def approve_selected(self, request, queryset):
        for obj in queryset:
            obj.approve()

    @admin.action(description="Reject selected affiliates")
    def reject_selected(self, request, queryset):
        for obj in queryset:
            obj.reject("Rejected by admin")


@admin.register(AffiliateLink)
class AffiliateLinkAdmin(admin.ModelAdmin):
    list_display = ["affiliate", "event", "commission_rate", "clicks", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["affiliate__affiliate_name", "event__event_title"]


@admin.register(AffiliateSale)
class AffiliateSaleAdmin(admin.ModelAdmin):
    list_display = [
        "affiliate",
        "event",
        "buyer",
        "gross_amount",
        "commission_amount",
        "status",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["affiliate__affiliate_name", "buyer__email", "event__event_title"]
