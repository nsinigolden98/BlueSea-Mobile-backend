from rest_framework import serializers
from .models import EventInfo, TicketType, IssuedTicket, TicketVendor, VendorKYC, EventScanner

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class TicketTypeSerializer(serializers.ModelSerializer):
    """Serializer for ticket types"""
    class Meta:
        model = TicketType
        fields = ['id', 'name', 'price', 'quantity_available', 'created_at']
        read_only_fields = ['id', 'created_at']


class VendorSerializer(serializers.ModelSerializer):
    """Serializer for vendor basic info"""
    class Meta:
        model = TicketVendor
        fields = '__all__'
        read_only_fields = ['id', 'is_verified']


class EventInfoSerializer(serializers.ModelSerializer):
    """Serializer for event listing and details"""
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = EventInfo
        fields = [
            'id', 'vendor', 'vendor_id', 'event_title', 'hosted_by', 
            'category', 'event_banner', 'ticket_image', 'event_date', 
            'event_location', 'event_description', 'is_free', 'is_approved', 
            'created_at', 'ticket_types'
        ]
        read_only_fields = ['id', 'is_approved', 'created_at', 'vendor']
    
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
    """Serializer for creating events with ticket types"""
    ticket_type_name = serializers.CharField(max_length=255, required=False, default='General Admission')
    ticket_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    ticket_quantity = serializers.IntegerField(required=False)
    vendor_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = EventInfo
        fields = [
            'vendor_id', 'event_title', 'hosted_by', 'category', 
            'event_banner', 'ticket_image', 'event_date', 'event_location', 
            'event_description', 'is_free', 'ticket_type_name', 
            'ticket_price', 'ticket_quantity'
        ]
    
    def validate_event_date(self, value):
        """Validate that event date is in the future"""
        if value < timezone.now():
            raise serializers.ValidationError("Event date must be in the future")
        return value
    
    def validate(self, data):
        """Validate event data"""
        is_free = data.get('is_free', False)
        
        if not is_free:
            # Paid events must have ticket information
            if not data.get('ticket_price') or not data.get('ticket_quantity'):
                raise serializers.ValidationError(
                    "Paid events must have ticket price and quantity"
                )
            if data.get('ticket_price') <= 0:
                raise serializers.ValidationError("Ticket price must be greater than 0")
            if data.get('ticket_quantity') <= 0:
                raise serializers.ValidationError("Ticket quantity must be greater than 0")
        
        # If free event, price should be 0
        if is_free and data.get('ticket_price') and data['ticket_price'] > 0:
            raise serializers.ValidationError(
                "Free events cannot have a ticket price greater than 0"
            )
        
        return data
    
    def create(self, validated_data):
        """Create event with ticket type"""
        # Extract ticket data
        ticket_type_name = validated_data.pop('ticket_type_name', 'General Admission')
        ticket_price = validated_data.pop('ticket_price', 0)
        ticket_quantity = validated_data.pop('ticket_quantity', 0)
        vendor_id = validated_data.pop('vendor_id', None)
        
        # Get or create vendor
        if vendor_id:
            try:
                vendor = TicketVendor.objects.get(id=vendor_id)
            except TicketVendor.DoesNotExist:
                raise serializers.ValidationError("Vendor not found")
        else:
            # For testing/admin purposes, create a default vendor
            vendor, created = TicketVendor.objects.get_or_create(
                brand_name=validated_data.get('hosted_by', 'Default Organizer'),
                defaults={'is_verified': True}
            )
        
        # If free event, set price to 0
        if validated_data.get('is_free'):
            ticket_price = 0
            if ticket_quantity == 0:
                ticket_quantity = 1000  # Default quantity for free events
        
        # Create event
        event = EventInfo.objects.create(vendor=vendor, **validated_data)
        
        # Create default ticket type
        TicketType.objects.create(
            event=event,
            name=ticket_type_name,
            price=ticket_price,
            quantity_available=ticket_quantity
        )
        
        return event


class AttendeeSerializer(serializers.Serializer):
    """Serializer for attendee information"""
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()


class PurchaseTicketSerializer(serializers.Serializer):
    """Serializer for ticket purchase request"""
    ticket_type_id = serializers.UUIDField()
    attendees = AttendeeSerializer(many=True)
    
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
    """Serializer for issued tickets"""
    ticket_type = TicketTypeSerializer(read_only=True)
    event = EventInfoSerializer(read_only=True)
    
    class Meta:
        model = IssuedTicket
        fields = [
            'id', 'ticket_type', 'event', 'owner_name', 'owner_email',
            'qr_code', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'qr_code', 'status', 'created_at']


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