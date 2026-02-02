from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from .models import (
    TicketVendor, VendorKYC, 
    EventInfo, TicketType, IssuedTicket, EventScanner
)

# Register your models here.

@admin.register(TicketVendor)
class TicketVendorAdmin(admin.ModelAdmin):
    list_display = [
        'brand_name', 'email', 'legal_full_name',
        'is_verified', 'created_at'
    ]
    list_filter = ['is_verified', 'created_at']
    search_fields = ['brand_name', 'legal_full_name', 'email', 'phone_number']
    readonly_fields = ['id', 'created_at']
    
    fieldsets = (
        ('Vendor Information', {
            'fields': (
                'id', 'legal_full_name', 'brand_name',
                'phone_number', 'email'
            )
        }),
        ('Location', {
            'fields': ('residential_address', 'state', 'city')
        }),
        ('Verification', {
            'fields': ('is_verified', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_vendors', 'reject_vendors_action']
    
    def approve_vendors(self, request, queryset):
        """Approve selected vendor verification requests"""
        approved_count = 0
        for vendor in queryset.filter(is_verified=False):
            vendor.is_verified = True
            vendor.rejection_reason = None
            vendor.save()
            
            approved_count += 1
        
        self.message_user(
            request,
            f'Successfully approved {approved_count} vendor(s)',
            messages.SUCCESS
        )
    approve_vendors.short_description = '✅ Approve selected vendors'
    
    def reject_vendors_action(self, request, queryset):
        """Reject selected vendors - prompts for reason"""
        selected = queryset.filter(is_verified=False).values_list('id', flat=True)
        selected_ids = ','.join(str(pk) for pk in selected)
        
        # Redirect to custom rejection view
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f'/market_place/admin/reject-vendors/?ids={selected_ids}')
    
    reject_vendors_action.short_description = '❌ Reject selected vendors'


@admin.register(VendorKYC)
class VendorKYCAdmin(admin.ModelAdmin):
    list_display = ['vendor_link', 'document_type', 'document_number', 'status', 'submitted_at', 'reviewed_at']
    list_filter = ['status', 'submitted_at', 'reviewed_at']
    search_fields = ['vendor__brand_name', 'document_type', 'document_number']
    readonly_fields = ['id', 'submitted_at', 'document_image_preview', 'proof_of_address_preview']
    list_per_page = 25
    date_hierarchy = 'submitted_at'
    actions = ['approve_kyc', 'reject_kyc']
    
    fieldsets = (
        ('Vendor Information', {
            'fields': ('id', 'vendor')
        }),
        ('Document Information', {
            'fields': ('document_type', 'document_number', 'document_image', 'document_image_preview')
        }),
        ('Proof of Address', {
            'fields': ('proof_of_address', 'proof_of_address_preview')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'reviewed_at')
        }),
    )
    
    def vendor_link(self, obj):
        url = reverse('admin:market_place_ticketvendor_change', args=[obj.vendor.id])
        return format_html('<a href="{}">{}</a>', url, obj.vendor.brand_name)
    vendor_link.short_description = 'Vendor'
    
    def document_image_preview(self, obj):
        if obj.document_image:
            if obj.document_image.name.endswith('.pdf'):
                return format_html('<a href="{}" target="_blank">📄 View PDF</a>', obj.document_image.url)
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 200px;"/></a>', 
                             obj.document_image.url, obj.document_image.url)
        return "No document"
    document_image_preview.short_description = 'Document Preview'
    
    def proof_of_address_preview(self, obj):
        if obj.proof_of_address:
            if obj.proof_of_address.name.endswith('.pdf'):
                return format_html('<a href="{}" target="_blank">🏠 View PDF</a>', obj.proof_of_address.url)
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 200px;"/></a>', 
                             obj.proof_of_address.url, obj.proof_of_address.url)
        return "No document"
    proof_of_address_preview.short_description = 'Proof of Address Preview'
    
    def approve_kyc(self, request, queryset):
        updated = queryset.update(status='approved', reviewed_at=timezone.now())
        vendor_ids = queryset.values_list('vendor_id', flat=True)
        TicketVendor.objects.filter(id__in=vendor_ids).update(is_verified=True)
        self.message_user(request, f'{updated} KYC application(s) approved and vendor(s) verified.', messages.SUCCESS)
    approve_kyc.short_description = 'Approve selected KYC applications'
    
    def reject_kyc(self, request, queryset):
        updated = queryset.update(status='rejected', reviewed_at=timezone.now())
        vendor_ids = queryset.values_list('vendor_id', flat=True)
        TicketVendor.objects.filter(id__in=vendor_ids).update(is_verified=False)
        self.message_user(request, f'{updated} KYC application(s) rejected.', messages.WARNING)
    reject_kyc.short_description = 'Reject selected KYC applications'


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ['name', 'price', 'quantity_available']


@admin.register(EventInfo)
class EventInfoAdmin(admin.ModelAdmin):
    list_display = ['event_title', 'hosted_by', 'category', 'event_date', 'event_location', 
                    'is_free', 'is_approved', 'vendor_link', 'created_at']
    list_filter = ['category', 'is_free', 'is_approved', 'event_date', 'created_at']
    search_fields = ['event_title', 'hosted_by', 'event_location', 'event_description', 'vendor__brand_name']
    readonly_fields = ['id', 'created_at', 'banner_preview', 'ticket_image_preview']
    list_per_page = 25
    date_hierarchy = 'event_date'
    inlines = [TicketTypeInline]
    actions = ['approve_events', 'unapprove_events']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('id', 'vendor', 'event_title', 'hosted_by', 'category')
        }),
        ('Event Details', {
            'fields': ('event_description', 'event_location', 'event_date')
        }),
        ('Images', {
            'fields': ('event_banner', 'banner_preview', 'ticket_image', 'ticket_image_preview')
        }),
        ('Ticket Info', {
            'fields': ('is_free',)
        }),
        ('Approval', {
            'fields': ('is_approved',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def vendor_link(self, obj):
        url = reverse('admin:market_place_ticketvendor_change', args=[obj.vendor.id])
        return format_html('<a href="{}">{}</a>', url, obj.vendor.brand_name)
    vendor_link.short_description = 'Vendor'
    
    def banner_preview(self, obj):
        if obj.event_banner:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 200px;"/></a>', 
                             obj.event_banner.url, obj.event_banner.url)
        return "No banner"
    banner_preview.short_description = 'Banner Preview'
    
    def ticket_image_preview(self, obj):
        if obj.ticket_image:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 200px;"/></a>', 
                             obj.ticket_image.url, obj.ticket_image.url)
        return "No ticket image"
    ticket_image_preview.short_description = 'Ticket Image Preview'
    
    def approve_events(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} event(s) approved successfully.', messages.SUCCESS)
    approve_events.short_description = 'Approve selected events'
    
    def unapprove_events(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} event(s) unapproved.', messages.WARNING)
    unapprove_events.short_description = 'Unapprove selected events'


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_link', 'price', 'quantity_available', 'created_at']
    list_filter = ['created_at', 'event__category']
    search_fields = ['name', 'event__event_title']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Ticket Type Information', {
            'fields': ('id', 'event', 'name')
        }),
        ('Pricing & Availability', {
            'fields': ('price', 'quantity_available')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def event_link(self, obj):
        url = reverse('admin:market_place_eventinfo_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.event_title)
    event_link.short_description = 'Event'


@admin.register(IssuedTicket)
class IssuedTicketAdmin(admin.ModelAdmin):
    list_display = ['short_id', 'owner_name', 'owner_email', 'event_link', 'ticket_type_link', 
                    'status', 'purchased_by_link', 'created_at']
    list_filter = ['status', 'created_at', 'event__category']
    search_fields = ['owner_name', 'owner_email', 'qr_code', 'event__event_title']
    readonly_fields = ['id', 'qr_code', 'created_at']
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['mark_as_used', 'mark_as_unused']
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('id', 'qr_code', 'ticket_type', 'event', 'status')
        }),
        ('Owner Information', {
            'fields': ('owner_name', 'owner_email', 'purchased_by')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'
    
    def event_link(self, obj):
        url = reverse('admin:market_place_eventinfo_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.event_title)
    event_link.short_description = 'Event'
    
    def ticket_type_link(self, obj):
        url = reverse('admin:market_place_tickettype_change', args=[obj.ticket_type.id])
        return format_html('<a href="{}">{}</a>', url, obj.ticket_type.name)
    ticket_type_link.short_description = 'Ticket Type'
    
    def purchased_by_link(self, obj):
        return obj.purchased_by.email if obj.purchased_by else '-'
    purchased_by_link.short_description = 'Purchased By'
    
    def mark_as_used(self, request, queryset):
        updated = queryset.update(status='used')
        self.message_user(request, f'{updated} ticket(s) marked as used.', messages.SUCCESS)
    mark_as_used.short_description = 'Mark selected tickets as used'
    
    def mark_as_unused(self, request, queryset):
        updated = queryset.update(status='unused')
        self.message_user(request, f'{updated} ticket(s) marked as unused.', messages.WARNING)
    mark_as_unused.short_description = 'Mark selected tickets as unused'


@admin.register(EventScanner)
class EventScannerAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'event_link', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'user__email', 'event__event_title']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Scanner Assignment', {
            'fields': ('id', 'user', 'event')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def event_link(self, obj):
        url = reverse('admin:market_place_eventinfo_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.event_title)
    event_link.short_description = 'Event'
