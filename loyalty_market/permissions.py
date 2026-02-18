from rest_framework.permissions import BasePermission
from loyalty_market.models import TicketVendor, EventScanner


class IsAdminOrVerifiedVendor(BasePermission):
    """
    Permission class to allow only admin users or verified vendors to create events.
    """
    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        
        # Check if user is a verified vendor
        try:
            vendor = TicketVendor.objects.get(id=request.data.get('vendor_id'))
            return vendor.is_verified
        except TicketVendor.DoesNotExist:
            return False


class IsEventOwnerOrAdmin(BasePermission):
    """
    Permission class to allow only event owner or admin to access event data.
    """
    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user and request.user.is_staff:
            return True
        
        # Check if user is the vendor who owns the event
        return obj.vendor.id == request.data.get('vendor_id')


class IsEventScanner(BasePermission):
    """
    Permission class to allow only assigned event scanners to scan tickets.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        event_id = request.data.get('event_id')
        if not event_id:
            return False
        
        # Check if user is assigned as a scanner for this event
        return EventScanner.objects.filter(
            user=request.user,
            event_id=event_id
        ).exists()