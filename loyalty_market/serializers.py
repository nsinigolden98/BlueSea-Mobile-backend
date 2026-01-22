from rest_framework import serializers
from loyalty_market.models import Reward, EventInfo, TicketType, IssuedTicket, TicketVendor, VendorKYC, EventScanner
from django.contrib.auth import get_user_model

User = get_user_model()


class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = '__all__'
        required_fields = ('title', 'description', 'points_cost', 'category')
        read_only_fields = ('id', 'created_at', 'user')


class RedeemPointsSerializer(serializers.Serializer):
    points = serializers.IntegerField(min_value=1)

    def validate_points(self, value):
        if value <= 0:
            raise serializers.ValidationError("Points must be a positive integer")
        return value


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
        fields = ['id', 'brand_name', 'is_verified']
        read_only_fields = ['id', 'is_verified']


class EventInfoSerializer(serializers.ModelSerializer):
    """Serializer for event listing and details"""
    ticket_types = TicketTypeSerializer(many=True, read_only=True)
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = EventInfo
        fields = [
            'id', 'vendor', 'vendor_id', 'event_name', 'event_image',
            'event_date', 'event_location', 'event_description',
            'is_free', 'is_approved', 'created_at', 'ticket_types'
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


class CreateEventSerializer(serializers.ModelSerializer):
    """Serializer for creating events with ticket types"""
    ticket_types = TicketTypeSerializer(many=True, required=False)
    vendor_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = EventInfo
        fields = [
            'vendor_id', 'event_name', 'event_image', 'event_date',
            'event_location', 'event_description', 'is_free', 'ticket_types'
        ]
    
    def validate(self, data):
        """Validate event data"""
        if not data.get('is_free') and not data.get('ticket_types'):
            raise serializers.ValidationError(
                "Paid events must have at least one ticket type"
            )
        return data
    
    def create(self, validated_data):
        """Create event with ticket types"""
        ticket_types_data = validated_data.pop('ticket_types', [])
        vendor_id = validated_data.pop('vendor_id')
        
        # Get vendor
        vendor = TicketVendor.objects.get(id=vendor_id)
        
        # Create event
        event = EventInfo.objects.create(vendor=vendor, **validated_data)
        
        # Create ticket types
        for ticket_type_data in ticket_types_data:
            TicketType.objects.create(event=event, **ticket_type_data)
        
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