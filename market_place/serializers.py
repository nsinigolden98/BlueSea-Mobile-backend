from rest_framework import serializers
from .models import EventInfo, TicketType, IssuedTicket, TicketVendor, VendorKYC, EventScanner

from django.contrib.auth import get_user_model
from django.utils import timezone
import base64
from django.core.files.base import ContentFile

User = get_user_model()

class TicketTypeSerializer(serializers.ModelSerializer):
    """Serializer for ticket types"""
    class Meta:
        model = TicketType
        fields = ['id', 'name', 'price', 'quantity_available', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class VendorSerializer(serializers.ModelSerializer):
    """Serializer for vendor basic info"""
    class Meta:
        model = TicketVendor
        fields = '__all__'
        read_only_fields = ['id', 'is_verified']


class VendorPublicSerializer(serializers.ModelSerializer):
    """Serializer for public vendor info (non-sensitive)"""
    class Meta:
        model = TicketVendor
        fields = ['id', 'brand_name', 'business_type', 'is_verified', 'verification_status']
        read_only_fields = fields


class EventInfoSerializer(serializers.ModelSerializer):
    """Serializer for event details"""
    vendor = VendorPublicSerializer(read_only=True)  # Changed from VendorSerializer
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    total_tickets = serializers.SerializerMethodField()
    tickets_sold = serializers.SerializerMethodField()
    
    class Meta:
        model = EventInfo
        fields = [
            'id', 'slug', 'vendor', 'event_title', 'event_description', 'event_date',
            'event_location', 'hosted_by', 'category', 'is_free', 'event_banner',
            'ticket_image', 'is_approved', 'ticket_types', 'total_tickets', 
            'tickets_sold', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'vendor', 'is_approved', 'ticket_types', 'created_at']
    
    def get_total_tickets(self, obj):
        """Calculate total tickets across all types"""
        return sum(tt.quantity_available for tt in obj.ticket_types.all())
    
    def get_tickets_sold(self, obj):
        """Calculate tickets sold"""
        issued = obj.issued_tickets.exclude(status='canceled').count()
        return issued

    def validate_vendor_id(self, value):
        """Validate that vendor exists and is verified"""
        try:
            vendor = TicketVendor.objects.get(id=value)
            if not vendor.is_verified:
                raise serializers.ValidationError("Vendor must be verified to create events")
            return value
        except TicketVendor.DoesNotExist:
            raise serializers.ValidationError("Vendor does not exist")
    
    def validate_event_date(self, value):
        """Validate that event date is in the future"""
        if value < timezone.now():
            raise serializers.ValidationError("Event date must be in the future")
        return value


class CreateEventSerializer(serializers.ModelSerializer):
    """Serializer for creating events with multiple ticket types"""
    ticket_types = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text="Array of ticket types with name, price, quantity_available, and optional description"
    )
    
    class Meta:
        model = EventInfo
        fields = [
            'vendor', 'event_title', 'event_description', 'event_date',
            'event_location', 'hosted_by', 'category', 'is_free',
            'event_banner', 'ticket_image', 'ticket_types'
        ]
    
    def validate(self, data):
        """
        Custom validation for events
        """
        # Event date must be in the future
        if data.get('event_date'):
            if data['event_date'] < timezone.now():
                raise serializers.ValidationError({
                    'event_date': 'Event date must be in the future'
                })
        
        # Validate ticket types for paid events
        is_free = data.get('is_free', False)
        ticket_types = data.get('ticket_types', [])
        
        # For free events, ticket_types should be empty or not provided
        if is_free:
            # If ticket_types is provided for free event, it must be empty
            if ticket_types and len(ticket_types) > 0:
                raise serializers.ValidationError({
                    'ticket_types': 'Free events should not have ticket types'
                })
            # Set to empty list to be safe
            data['ticket_types'] = []
            return data
        
        # For paid events, validate ticket types
        if not is_free and not ticket_types:
            raise serializers.ValidationError({
                'ticket_types': 'At least one ticket type is required for paid events'
            })
        
        # Limit to maximum 5 ticket types
        if len(ticket_types) > 5:
            raise serializers.ValidationError({
                'ticket_types': 'Maximum of 5 ticket types allowed per event'
            })
        
        # Validate each ticket type
        if ticket_types:
            seen_names = set()
            
            for idx, ticket_type in enumerate(ticket_types, 1):
                # Check required fields
                if not ticket_type.get('name'):
                    raise serializers.ValidationError({
                        'ticket_types': f'Ticket type {idx}: name is required'
                    })
                
                # Check for duplicate names
                ticket_name = ticket_type.get('name', '').strip().lower()
                if ticket_name in seen_names:
                    raise serializers.ValidationError({
                        'ticket_types': f'Ticket type {idx}: duplicate ticket name "{ticket_type.get("name")}"'
                    })
                seen_names.add(ticket_name)
                
                if not ticket_type.get('price'):
                    raise serializers.ValidationError({
                        'ticket_types': f'Ticket type {idx} ({ticket_type.get("name")}): price is required'
                    })
                
                if not ticket_type.get('quantity_available'):
                    raise serializers.ValidationError({
                        'ticket_types': f'Ticket type {idx} ({ticket_type.get("name")}): quantity_available is required'
                    })
                
                # Validate price is positive
                try:
                    price = float(ticket_type.get('price', 0))
                    if price <= 0:
                        raise serializers.ValidationError({
                            'ticket_types': f'Ticket type {idx} ({ticket_type.get("name")}): price must be greater than 0'
                        })
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'ticket_types': f'Ticket type {idx} ({ticket_type.get("name")}): invalid price format'
                    })
                
                # Validate quantity is positive integer
                try:
                    quantity = int(ticket_type.get('quantity_available', 0))
                    if quantity <= 0:
                        raise serializers.ValidationError({
                            'ticket_types': f'Ticket type {idx} ({ticket_type.get("name")}): quantity_available must be greater than 0'
                        })
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'ticket_types': f'Ticket type {idx} ({ticket_type.get("name")}): invalid quantity_available format'
                    })
        
        return data
    
    def create(self, validated_data):
        """
        Create event with multiple ticket types
        """
        ticket_types_data = validated_data.pop('ticket_types', [])
        
        # Create event
        event = EventInfo.objects.create(**validated_data)
        
        # Create ticket types only if event is paid
        if not event.is_free and ticket_types_data:
            # Sort by price ascending
            sorted_ticket_types = sorted(ticket_types_data, key=lambda x: float(x.get('price', 0)))
            
            for ticket_data in sorted_ticket_types:
                TicketType.objects.create(
                    event=event,
                    name=ticket_data.get('name').strip(),
                    price=ticket_data.get('price', 0),
                    quantity_available=ticket_data.get('quantity_available'),
                    description=ticket_data.get('description', '').strip()
                )
        
        return event


class AttendeeSerializer(serializers.Serializer):
    """Serializer for attendee information"""
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()


class PurchaseTicketSerializer(serializers.Serializer):
    """Serializer for ticket purchase request - event_id comes from URL"""
    ticket_type = serializers.CharField(
        required=False, 
        allow_null=True,
        allow_blank=True,
        help_text="Ticket type name (e.g., 'Regular', 'VIP', 'Early Bird'). Leave empty for free events."
    )
    quantity = serializers.IntegerField(required=True, min_value=1, max_value=10, help_text="Number of tickets (1-10)")
    transaction_pin = serializers.CharField(
        required=False, 
        allow_null=True,
        allow_blank=True,
        min_length=4, 
        max_length=6,
        help_text="Transaction PIN (required only for paid events)"
    )
    attendees = serializers.ListField(
        child=AttendeeSerializer(),
        required=False,
        allow_empty=True,
        help_text="List of attendees. Leave empty to use your own details."
    )
    
    def validate(self, data):
        request = self.context.get('request')
        event_id = self.context.get('event_id')
        quantity = data.get('quantity', 1)
        attendees = data.get('attendees', [])
        
        # Handle None or empty ticket_type safely
        ticket_type_raw = data.get('ticket_type')
        ticket_type_name = ticket_type_raw.strip() if ticket_type_raw else ''
        
        # Validate event exists
        try:
            event = EventInfo.objects.get(id=event_id)
        except EventInfo.DoesNotExist:
            raise serializers.ValidationError({'event': 'Event not found'})
        
        # Store event for later use
        data['event_obj'] = event
        
        # Validate ticket type for paid events
        if not event.is_free:
            if not ticket_type_name:
                raise serializers.ValidationError({
                    'ticket_type': 'Ticket type is required for paid events'
                })
            
            # Check if ticket type exists for this event
            try:
                ticket_type = TicketType.objects.get(
                    event=event,
                    name__iexact=ticket_type_name  # Case-insensitive match
                )
                data['ticket_type_obj'] = ticket_type
            except TicketType.DoesNotExist:
                # Get available ticket types for helpful error message
                available_types = list(TicketType.objects.filter(event=event).values_list('name', flat=True))
                raise serializers.ValidationError({
                    'ticket_type': f"Ticket type '{ticket_type_name}' not found. Available types: {', '.join(available_types)}"
                })
        else:
            # Free event - no ticket type needed
            if ticket_type_name:
                raise serializers.ValidationError({
                    'ticket_type': 'Free events do not require a ticket type'
                })
            data['ticket_type_obj'] = None
        
        # Auto-fill attendees if not provided
        if not attendees:
            if request and request.user.is_authenticated:
                # Get user's full name
                full_name = request.user.get_full_name()
                if not full_name or full_name.strip() == '':
                    full_name = f"{request.user.first_name} {request.user.last_name}".strip()
                if not full_name or full_name == '':
                    full_name = request.user.username or request.user.email.split('@')[0]
                
                user_attendee = {
                    'name': full_name,
                    'email': request.user.email
                }
                data['attendees'] = [user_attendee.copy() for _ in range(quantity)]
            else:
                raise serializers.ValidationError({
                    'attendees': 'Attendees information is required'
                })
        else:
            # Validate quantity matches attendees
            if len(attendees) != quantity:
                raise serializers.ValidationError({
                    'attendees': f'Number of attendees ({len(attendees)}) must match quantity ({quantity})'
                })
        
        return data

    def validate_attendees(self, value):
        """Validate attendee list"""
        if len(value) == 0:
            raise serializers.ValidationError("At least one attendee is required")
        if len(value) > 5:
            raise serializers.ValidationError("Maximum 5 attendees per purchase")
        return value
    
    def validate_ticket_type_id(self, value):
        """Validate ticket type exists"""
        try:
            TicketType.objects.get(id=value)
            return value
        except TicketType.DoesNotExist:
            raise serializers.ValidationError("Ticket type does not exist")


class IssuedTicketSerializer(serializers.ModelSerializer):
    """Serializer for issued tickets with minimal event info"""
    ticket_type = TicketTypeSerializer(read_only=True)
    event_title = serializers.CharField(source='event.event_title', read_only=True)
    event_date = serializers.DateTimeField(source='event.event_date', read_only=True)
    event_location = serializers.CharField(source='event.event_location', read_only=True)
    event_banner = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source='event.vendor.brand_name', read_only=True)
    is_free = serializers.BooleanField(source='event.is_free', read_only=True)
    
    class Meta:
        model = IssuedTicket
        fields = [
            'id', 'ticket_type', 'event_title', 'event_date', 'event_location',
            'event_banner', 'vendor_name', 'is_free', 'owner_name', 'owner_email',
            'qr_code', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'qr_code', 'status', 'created_at']
    
    def get_event_banner(self, obj):
        if obj.event.event_banner:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.event.event_banner.url)
        return None


class ScanTicketSerializer(serializers.Serializer):
    """Serializer for ticket scanning"""
    qr_code = serializers.CharField(max_length=255)
    event_id = serializers.UUIDField()


class AttendeeExportSerializer(serializers.Serializer):
    """Serializer for attendee export data"""
    name = serializers.CharField()
    email = serializers.EmailField()
    ticket_type = serializers.CharField()
    ticket_status = serializers.CharField()
    qr_code = serializers.CharField()
    purchase_date = serializers.DateTimeField()


class TicketListSerializer(serializers.ModelSerializer):
    """Serializer for listing tickets (basic info with ticket type details)"""
    event_title = serializers.CharField(source='event.event_title', read_only=True)
    event_date = serializers.DateTimeField(source='event.event_date', read_only=True)
    event_location = serializers.CharField(source='event.event_location', read_only=True)
    event_banner = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source='event.vendor.brand_name', read_only=True)
    
    # Ticket type information
    is_free = serializers.BooleanField(source='event.is_free', read_only=True)
    ticket_type_name = serializers.SerializerMethodField()
    ticket_type_price = serializers.SerializerMethodField()
    
    class Meta:
        model = IssuedTicket
        fields = [
            'id', 'event_title', 'event_date', 'event_location', 'event_banner',
            'is_free', 'ticket_type_name', 'ticket_type_price',
            'owner_name', 'owner_email', 'status', 'vendor_name',
            'created_at', 'transferred_at', 'canceled_at'
        ]
    
    def get_event_banner(self, obj):
        if obj.event.event_banner:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.event.event_banner.url)
        return None
    
    def get_ticket_type_name(self, obj):
        """Return ticket type name or 'Free Entry'"""
        if obj.event.is_free or not obj.ticket_type:
            return "Free Entry"
        return obj.ticket_type.name
    
    def get_ticket_type_price(self, obj):
        """Return ticket price or '0.00' for free tickets"""
        if obj.event.is_free or not obj.ticket_type:
            return "0.00"
        return str(obj.ticket_type.price)


class TicketDetailSerializer(serializers.ModelSerializer):
    event = EventInfoSerializer(read_only=True)
    ticket_type = TicketTypeSerializer(read_only=True)
    qr_code_base64 = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()
    can_transfer = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    refund_info = serializers.SerializerMethodField()
    scanned_by_email = serializers.EmailField(source='scanned_by.email', read_only=True)
    purchased_by_email = serializers.EmailField(source='purchased_by.email', read_only=True)
    
    class Meta:
        model = IssuedTicket
        fields = [
            'id', 'event', 'ticket_type', 'owner_name', 'owner_email',
            'qr_code', 'qr_code_base64', 'qr_code_url', 'status',
            'purchased_by_email', 'transferred_to', 'transferred_at', 'transfer_count',
            'canceled_at', 'refund_amount', 'cancellation_reason',
            'scanned_at', 'scanned_by_email', 'created_at', 'updated_at',
            'can_transfer', 'can_cancel', 'refund_info'
        ]
    
    def get_qr_code_base64(self, obj):
        if obj.qr_code_image:
            try:
                with obj.qr_code_image.open('rb') as image_file:
                    encoded = base64.b64encode(image_file.read()).decode('utf-8')
                    return f"data:image/png;base64,{encoded}"
            except Exception:
                return None
        return None
    
    def get_qr_code_url(self, obj):
        if obj.qr_code_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code_image.url)
            return obj.qr_code_image.url
        return None
    
    def get_can_transfer(self, obj):
        can_transfer, message = obj.can_transfer()
        return {
            'allowed': can_transfer,
            'message': message
        }
    
    def get_can_cancel(self, obj):
        can_cancel, refund_amount, message = obj.can_cancel()
        return {
            'allowed': can_cancel,
            'message': message
        }
    
    def get_refund_info(self, obj):
        if obj.status == 'canceled' and obj.refund_amount:
            return {
                'refund_amount': float(obj.refund_amount),
                'canceled_at': obj.canceled_at,
                'reason': obj.cancellation_reason
            }
        return None


class TransferTicketSerializer(serializers.Serializer):
    """Serializer for transferring tickets - ticket_id comes from URL"""
    recipient_email = serializers.EmailField(required=True, help_text="Recipient's email address")
    recipient_name = serializers.CharField(required=True, max_length=255, help_text="Recipient's full name")


class CancelTicketSerializer(serializers.Serializer):
    """Serializer for canceling tickets - ticket_id comes from URL"""
    reason = serializers.CharField(required=True, help_text="Reason for cancellation")
    transaction_pin = serializers.CharField(
        required=False,
        allow_blank=True,
        min_length=4,
        max_length=6,
        help_text="Transaction PIN (required for paid tickets only)"
    )