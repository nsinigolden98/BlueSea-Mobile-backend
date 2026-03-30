from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from .models import TicketVendor, VendorKYC, EventInfo, TicketType, IssuedTicket, EventScanner


def _bool_badge(value, true_label='Yes', false_label='No'):
    if value:
        return format_html(
            '<span style="background:#d4edda;color:#155724;padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;">{}</span>', true_label
        )
    return format_html(
        '<span style="background:#f8d7da;color:#721c24;padding:3px 10px;border-radius:12px;'
        'font-size:11px;font-weight:600;">{}</span>', false_label
    )


@admin.register(TicketVendor)
class TicketVendorAdmin(admin.ModelAdmin):
    list_display = [
        'brand_name', 'email', 'legal_full_name',
        'verification_badge', 'created_at'
    ]
    list_filter = ['is_verified', 'created_at']
    search_fields = ['brand_name', 'legal_full_name', 'email', 'phone_number']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25
    actions = ['approve_vendors', 'reject_vendors_action']

    fieldsets = (
        ('Vendor Information', {
            'fields': ('id', 'legal_full_name', 'brand_name', 'phone_number', 'email')
        }),
        ('Location', {
            'fields': ('residential_address', 'state', 'city')
        }),
        ('Verification', {
            'fields': ('is_verified', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at',), 'classes': ('collapse',)
        }),
    )

    def verification_badge(self, obj):
        return _bool_badge(obj.is_verified, 'Verified', 'Pending')
    verification_badge.short_description = 'Verification'

    def approve_vendors(self, request, queryset):
        approved_count = 0
        for vendor in queryset.filter(is_verified=False):
            vendor.is_verified = True
            vendor.rejection_reason = None
            vendor.save()
            approved_count += 1
        self.message_user(request, f'Successfully approved {approved_count} vendor(s).', messages.SUCCESS)
    approve_vendors.short_description = 'Approve selected vendors'

    def reject_vendors_action(self, request, queryset):
        selected = queryset.filter(is_verified=False).values_list('id', flat=True)
        selected_ids = ','.join(str(pk) for pk in selected)
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f'/market_place/admin/reject-vendors/?ids={selected_ids}')
    reject_vendors_action.short_description = 'Reject selected vendors'


@admin.register(VendorKYC)
class VendorKYCAdmin(admin.ModelAdmin):
    list_display = [
        'vendor_link', 'document_type', 'document_number',
        'kyc_status_badge', 'submitted_at', 'reviewed_at'
    ]
    list_filter = ['status', 'submitted_at', 'reviewed_at']
    search_fields = ['vendor__brand_name', 'document_type', 'document_number']
    readonly_fields = ['id', 'submitted_at', 'document_image_preview', 'proof_of_address_preview']
    list_per_page = 25
    date_hierarchy = 'submitted_at'
    actions = ['approve_kyc', 'reject_kyc']

    fieldsets = (
        ('Vendor', {'fields': ('id', 'vendor')}),
        ('Document', {
            'fields': ('document_type', 'document_number', 'document_image', 'document_image_preview')
        }),
        ('Proof of Address', {
            'fields': ('proof_of_address', 'proof_of_address_preview')
        }),
        ('Review', {'fields': ('status',)}),
        ('Timestamps', {'fields': ('submitted_at', 'reviewed_at'), 'classes': ('collapse',)}),
    )

    def vendor_link(self, obj):
        url = reverse('admin:market_place_ticketvendor_change', args=[obj.vendor.id])
        return format_html('<a href="{}">{}</a>', url, obj.vendor.brand_name)
    vendor_link.short_description = 'Vendor'

    def kyc_status_badge(self, obj):
        status_colors = {
            'approved': ('#d4edda', '#155724'),
            'pending': ('#fff3cd', '#856404'),
            'rejected': ('#f8d7da', '#721c24'),
        }
        bg, text = status_colors.get(obj.status.lower(), ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.status
        )
    kyc_status_badge.short_description = 'KYC Status'

    def document_image_preview(self, obj):
        if obj.document_image:
            if obj.document_image.name.endswith('.pdf'):
                return format_html('<a href="{}" target="_blank">View PDF Document</a>', obj.document_image.url)
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:200px;border-radius:4px;"/></a>',
                obj.document_image.url, obj.document_image.url
            )
        return 'No document uploaded'
    document_image_preview.short_description = 'Document Preview'

    def proof_of_address_preview(self, obj):
        if obj.proof_of_address:
            if obj.proof_of_address.name.endswith('.pdf'):
                return format_html('<a href="{}" target="_blank">View PDF</a>', obj.proof_of_address.url)
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:200px;border-radius:4px;"/></a>',
                obj.proof_of_address.url, obj.proof_of_address.url
            )
        return 'No document uploaded'
    proof_of_address_preview.short_description = 'Address Proof Preview'

    def approve_kyc(self, request, queryset):
        updated = queryset.update(status='approved', reviewed_at=timezone.now())
        vendor_ids = queryset.values_list('vendor_id', flat=True)
        TicketVendor.objects.filter(id__in=vendor_ids).update(is_verified=True)
        self.message_user(request, f'{updated} KYC application(s) approved.', messages.SUCCESS)
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
    list_display = [
        'event_title', 'hosted_by', 'category',
        'event_date_display', 'event_location',
        'free_badge', 'approval_badge', 'vendor_link', 'created_at'
    ]
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
        ('Settings', {'fields': ('is_free',)}),
        ('Approval', {'fields': ('is_approved',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def event_date_display(self, obj):
        now = timezone.now().date()
        days_diff = (obj.event_date.date() - now).days if hasattr(obj.event_date, 'date') else (obj.event_date - now).days
        if days_diff < 0:
            label = format_html(
                '<span style="color:#6c757d;font-size:11px;">Past event</span>'
            )
        elif days_diff == 0:
            label = format_html('<span style="color:#fd7e14;font-weight:600;">Today</span>')
        elif days_diff <= 3:
            label = format_html('<span style="color:#ffc107;font-weight:600;">In {} day(s)</span>', days_diff)
        else:
            label = format_html('<span style="color:#28a745;">{}</span>', obj.event_date)
        return label
    event_date_display.short_description = 'Event Date'

    def free_badge(self, obj):
        return _bool_badge(obj.is_free, 'Free', 'Paid')
    free_badge.short_description = 'Ticket'

    def approval_badge(self, obj):
        return _bool_badge(obj.is_approved, 'Approved', 'Pending')
    approval_badge.short_description = 'Approval'

    def vendor_link(self, obj):
        url = reverse('admin:market_place_ticketvendor_change', args=[obj.vendor.id])
        return format_html('<a href="{}">{}</a>', url, obj.vendor.brand_name)
    vendor_link.short_description = 'Vendor'

    def banner_preview(self, obj):
        if obj.event_banner:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:200px;border-radius:6px;"/></a>',
                obj.event_banner.url, obj.event_banner.url
            )
        return 'No banner uploaded'
    banner_preview.short_description = 'Banner Preview'

    def ticket_image_preview(self, obj):
        if obj.ticket_image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:200px;border-radius:6px;"/></a>',
                obj.ticket_image.url, obj.ticket_image.url
            )
        return 'No ticket image'
    ticket_image_preview.short_description = 'Ticket Image Preview'

    def approve_events(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} event(s) approved.', messages.SUCCESS)
    approve_events.short_description = 'Approve selected events'

    def unapprove_events(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} event(s) unapproved.', messages.WARNING)
    unapprove_events.short_description = 'Unapprove selected events'


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_link', 'price_display', 'quantity_available', 'created_at']
    list_filter = ['created_at', 'event__category']
    search_fields = ['name', 'event__event_title']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25

    fieldsets = (
        ('Ticket Type', {'fields': ('id', 'event', 'name')}),
        ('Pricing & Availability', {'fields': ('price', 'quantity_available')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def event_link(self, obj):
        url = reverse('admin:market_place_eventinfo_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.event_title)
    event_link.short_description = 'Event'

    def price_display(self, obj):
        if obj.price == 0:
            return format_html('<span style="color:#28a745;font-weight:600;">Free</span>')
        return format_html(
            '<span style="font-family:monospace;font-weight:600;">&#x20A6;{}</span>',
            f'{float(obj.price):,.2f}'
        )
    price_display.short_description = 'Price'


@admin.register(IssuedTicket)
class IssuedTicketAdmin(admin.ModelAdmin):
    list_display = [
        'short_id', 'owner_name', 'owner_email', 'event_link',
        'ticket_type_link', 'ticket_status_badge', 'transfer_count',
        'purchased_by_link', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'event__category', 'transferred_at', 'canceled_at']
    search_fields = ['owner_name', 'owner_email', 'qr_code', 'event__event_title']
    readonly_fields = ['id', 'qr_code', 'qr_code_preview', 'created_at', 'updated_at']
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['mark_as_used', 'mark_as_expired', 'regenerate_qr_codes']

    fieldsets = (
        ('Ticket Info', {
            'fields': ('id', 'qr_code', 'qr_code_image', 'qr_code_preview', 'ticket_type', 'event', 'status')
        }),
        ('Owner', {'fields': ('owner_name', 'owner_email', 'purchased_by')}),
        ('Transfer', {
            'fields': ('transferred_to', 'transferred_at', 'transfer_count'),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('canceled_at', 'refund_amount', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Scan Info', {
            'fields': ('scanned_at', 'scanned_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def short_id(self, obj):
        return str(obj.id)[:8].upper()
    short_id.short_description = 'ID'

    def ticket_status_badge(self, obj):
        status_map = {
            'active': ('#d4edda', '#155724'),
            'used': ('#d1ecf1', '#0c5460'),
            'expired': ('#e2e3e5', '#383d41'),
            'cancelled': ('#f8d7da', '#721c24'),
            'transferred': ('#fff3cd', '#856404'),
        }
        bg, text = status_map.get(obj.status.lower(), ('#e2e3e5', '#383d41'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
            'font-size:11px;font-weight:600;text-transform:uppercase;">{}</span>',
            bg, text, obj.status
        )
    ticket_status_badge.short_description = 'Status'

    def event_link(self, obj):
        url = reverse('admin:market_place_eventinfo_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.event_title)
    event_link.short_description = 'Event'

    def ticket_type_link(self, obj):
        url = reverse('admin:market_place_tickettype_change', args=[obj.ticket_type.id])
        return format_html('<a href="{}">{}</a>', url, obj.ticket_type.name)
    ticket_type_link.short_description = 'Ticket Type'

    def purchased_by_link(self, obj):
        if obj.purchased_by:
            url = reverse('admin:accounts_profile_change', args=[obj.purchased_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.purchased_by.email)
        return '—'
    purchased_by_link.short_description = 'Purchased By'

    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:200px;border-radius:4px;"/></a>',
                obj.qr_code_image.url, obj.qr_code_image.url
            )
        return 'No QR code'
    qr_code_preview.short_description = 'QR Code Preview'

    def mark_as_used(self, request, queryset):
        updated = queryset.update(status='used', scanned_at=timezone.now())
        self.message_user(request, f'{updated} ticket(s) marked as used.', messages.SUCCESS)
    mark_as_used.short_description = 'Mark as used'

    def mark_as_expired(self, request, queryset):
        updated = queryset.update(status='expired')
        self.message_user(request, f'{updated} ticket(s) marked as expired.', messages.WARNING)
    mark_as_expired.short_description = 'Mark as expired'

    def regenerate_qr_codes(self, request, queryset):
        from .utils import generate_ticket_qr_code
        count = 0
        for ticket in queryset:
            try:
                generate_ticket_qr_code(ticket)
                count += 1
            except Exception as e:
                self.message_user(request, f'QR generation failed for {ticket.id}: {e}', messages.ERROR)
        self.message_user(request, f'Regenerated {count} QR code(s).', messages.SUCCESS)
    regenerate_qr_codes.short_description = 'Regenerate QR codes'


@admin.register(EventScanner)
class EventScannerAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'event_link', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'event__event_title']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25

    fieldsets = (
        ('Scanner Assignment', {'fields': ('id', 'user', 'event')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Scanner User'

    def event_link(self, obj):
        url = reverse('admin:market_place_eventinfo_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.event_title)
    event_link.short_description = 'Event'
