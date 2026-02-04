from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import (
    EventInfoSerializer,
    CreateEventSerializer, PurchaseTicketSerializer, IssuedTicketSerializer,
    ScanTicketSerializer, AttendeeExportSerializer
)
from .models import (
    EventInfo, TicketType, 
    IssuedTicket, TicketVendor, EventScanner
)
import logging
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
import secrets
from django.db import transaction
import csv
from wallet.models import Wallet
from bonus.models import BonusPoint
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__)

# ============= TICKETING SYSTEM VIEWS =============

class CreateEventView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create a new event",
        description="Create a new event with ticket information. Only admin or verified vendors can create events.",
        request=CreateEventSerializer,
        responses={
            201: EventInfoSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT
        },
        tags=['Ticketing']
    )
    def post(self, request):
        user = request.user
        
        # Check if user is admin
        is_admin = user.is_staff or user.is_superuser
        
        if not is_admin:
            # For non-admin users, vendor_id is required
            vendor_id = request.data.get('vendor_id')
            
            if not vendor_id:
                return Response(
                    {"error": "vendor_id is required for non-admin users"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if vendor exists and is verified
            try:
                vendor = TicketVendor.objects.get(id=vendor_id)
                if not vendor.is_verified:
                    return Response(
                        {"error": "Only verified vendors can create events. Please complete KYC verification."},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except TicketVendor.DoesNotExist:
                return Response(
                    {"error": "Vendor not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Proceed with event creation
        serializer = CreateEventSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    event = serializer.save()
                    logger.info(
                        f"Event '{event.event_title}' created by user {request.user.id}. "
                        f"Hosted by: {event.hosted_by}, Category: {event.category}, "
                        f"Vendor: {event.vendor.brand_name}"
                    )
                
                # Return complete event details with ticket types
                response_serializer = EventInfoSerializer(event)
                return Response(
                    {
                        "message": "Event created successfully. Awaiting admin approval." if not is_admin else "Event created successfully.",
                        "event": response_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            
            except Exception as e:
                logger.error(f"Event creation failed: {str(e)}")
                return Response(
                    {"error": f"Failed to create event: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        logger.error(f"Event creation validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateTicketVendor(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"Vendor creation request initiated by user {request.user.id}")
        logger.debug(f"Request data keys: {list(request.data.keys())}")
        logger.debug(f"Request files: {list(request.FILES.keys())}")
        
        try:
            if not request.user.pin_is_set:
                logger.warning(f"Vendor creation failed for user {request.user.id}: PIN not set")
                return Response(
                    {"error": "Please set your transaction PIN before creating a vendor account."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if TicketVendor.objects.filter(user=request.user).exists():
                logger.warning(f"Vendor creation failed for user {request.user.id}: Vendor already exists")
                return Response(
                    {"error": "You already have a ticket vendor account."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            business_type = request.data.get('business_type')
            brand_name = request.data.get('brand_name')
            residential_address = request.data.get('residential_address')
            state_city = request.data.get('state')
            id_type = request.data.get('id_type')
            monthly_volume = request.data.get('monthly_volume')
            business_description = request.data.get('business_description')

            logger.debug(f"Extracted fields - business_type: {business_type}, brand_name: {brand_name}, "
                        f"state_city: {state_city}, id_type: {id_type}")

            required_fields = {
                "business_type": business_type,
                "brand_name": brand_name,
                "residential_address": residential_address,
                "state_city": state_city,
                "id_type": id_type,
                "monthly_volume": monthly_volume,
                "business_description": business_description
            }

            missing_fields = [field for field, value in required_fields.items() if not value]
            if missing_fields:
                logger.warning(f"Vendor creation validation failed for user {request.user.id}: "
                             f"Missing fields: {', '.join(missing_fields)}")
                return Response(
                    {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # validate file uploads
            id_document = request.FILES.get('id_document')
            proof_of_address = request.FILES.get('proof_of_address')
            event_authorization = request.FILES.get('event_authorization')

            logger.debug(f"File validation - id_document: {bool(id_document)}, "
                        f"proof_of_address: {bool(proof_of_address)}, "
                        f"event_authorization: {bool(event_authorization)}")

            if not id_document:
                logger.warning(f"Vendor creation validation failed for user {request.user.id}: ID document missing")
                return Response(
                    {"error": "ID document upload is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not proof_of_address:
                logger.warning(f"Vendor creation validation failed for user {request.user.id}: Proof of address missing")
                return Response(
                    {'error': 'Proof of address not uploaded'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']

            if id_document.content_type not in allowed_types:
                logger.warning(f"Vendor creation validation failed for user {request.user.id}: "
                             f"Invalid ID document type: {id_document.content_type}")
                return Response(
                    {'error': 'Invalid ID document format. Allowed: PDF, JPEG, PNG', 'success': False},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if proof_of_address.content_type not in allowed_types:
                logger.warning(f"Vendor creation validation failed for user {request.user.id}: "
                             f"Invalid proof of address type: {proof_of_address.content_type}")
                return Response(
                    {'error': 'Invalid proof of address format. Allowed: PDF, JPEG, PNG', 'success': False},
                    status=status.HTTP_400_BAD_REQUEST
                )
            categories = request.data.get('categories', '')
            if isinstance(categories, str):
                categories = [cat.strip() for cat in categories.split(',') if cat.strip()]
            elif isinstance(categories, list):
                categories = categories
            else:
                categories = []

            # Parse state and city
            if state_city and ':' in state_city:
                state, city = state_city.split(':', 1)
            else:
                state = state_city
                city = ''

            logger.debug(f"Parsed location - state: {state}, city: {city}")
            logger.debug(f"Categories parsed: {categories}")
            
            legal_full_name = request.user.get_full_name() or request.user.username
            logger.info(f"Creating vendor for user {request.user.id} - brand_name: {brand_name}, "
                       f"legal_full_name: {legal_full_name}, business_type: {business_type}")

            # Create vendor profile with atomic transaction
            with transaction.atomic():
                vendor = TicketVendor.objects.create(
                    user=request.user,
                    business_type=business_type,
                    brand_name=brand_name,
                    legal_full_name=legal_full_name,
                    phone_number=request.user.phone,
                    email=request.user.email,
                    residential_address=residential_address,
                    state=state,
                    city=city,
                    id_type=id_type,
                    id_document=id_document,
                    proof_of_address=proof_of_address,
                    event_authorization=event_authorization,
                    categories=','.join(categories),
                    monthly_volume=monthly_volume,
                    business_description=business_description,
                    is_verified=False,
                    verification_status='pending'
                )

                logger.info(
                    f"Vendor profile successfully created for user {request.user.id}. "
                    f"Vendor ID: {vendor.id}, Brand: {brand_name}, Type: {business_type}, "
                    f"Status: {vendor.verification_status}, Email: {vendor.email}"
                )

                return Response(
                    {
                        'success': True,
                        'message': 'Verification request submitted successfully. Our team will review within 24-72 hours.',
                        'vendor': {
                            'id': vendor.id,
                            'brand_name': vendor.brand_name,
                            'verification_status': vendor.verification_status,
                            'created_at': vendor.created_at
                        }
                    },
                    status=status.HTTP_201_CREATED
                )

        except Exception as e:
            logger.error(f"Vendor creation failed for user {request.user.id}: {type(e).__name__}: {str(e)}", 
                        exc_info=True)
            return Response(
                {
                    'error': 'Failed to submit verification request. Please try again.',
                    'success': False,
                    'details': str(e) if request.user.is_staff else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class VendorStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get vendor verification status",
        description="Check the current verification status of your vendor profile",
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Ticketing']
    )
    def get(self, request):
        try:
            vendor = TicketVendor.objects.get(user=request.user)
            
            return Response(
                {
                    'success': True,
                    'vendor': {
                        'id': vendor.id,
                        'brand_name': vendor.brand_name,
                        'business_type': vendor.business_type,
                        'verification_status': vendor.verification_status,
                        'is_verified': vendor.is_verified,
                        'created_at': vendor.created_at,
                        'updated_at': vendor.updated_at
                    }
                },
                status=status.HTTP_200_OK
            )
        
        except TicketVendor.DoesNotExist:
            return Response(
                {
                    'error': 'No vendor profile found',
                    'success': False
                },
                status=status.HTTP_404_NOT_FOUND
            )



class EventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all approved events",
        description="Get all approved events with ticket types and pricing information. Optionally filter by category.",
        parameters=[
            OpenApiParameter(
                name='category',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by category (Music, Conference, Sports, Networking)'
            )
        ],
        responses={200: EventInfoSerializer(many=True)},
        tags=['Ticketing']
    )
    def get(self, request):
        # Base query: only approved events
        events = EventInfo.objects.filter(is_approved=True).prefetch_related('ticket_types')
        
        # Filter by category if provided
        category = request.query_params.get('category')
        if category:
            events = events.filter(category=category)
        
        serializer = EventInfoSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EventDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get event details",
        description="Retrieve detailed information about a specific event including available ticket types",
        parameters=[
            OpenApiParameter(name='event_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH)
        ],
        responses={200: EventInfoSerializer, 404: OpenApiTypes.OBJECT},
        tags=['Ticketing']
    )
    def get(self, request, event_id):
        event = get_object_or_404(EventInfo, id=event_id, is_approved=True)
        serializer = EventInfoSerializer(event)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PurchaseTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Purchase event tickets",
        description="Purchase tickets for an event. Max 5 attendees per purchase. Deducts from wallet balance.",
        request=PurchaseTicketSerializer,
        responses={201: IssuedTicketSerializer(many=True), 400: OpenApiTypes.OBJECT},
        tags=['Ticketing']
    )
    def post(self, request):
        serializer = PurchaseTicketSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ticket_type_id = serializer.validated_data['ticket_type_id']
        attendees = serializer.validated_data['attendees']
        user = request.user
        
        # Use atomic transaction to ensure data consistency
        try:
            with transaction.atomic():
                # Get ticket type with select_for_update to prevent race conditions
                ticket_type = TicketType.objects.select_for_update().get(id=ticket_type_id)
                event = ticket_type.event
                
                # Validate event is approved
                if not event.is_approved:
                    return Response(
                        {"error": "Event is not approved for ticket sales"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate ticket availability
                num_tickets = len(attendees)
                if ticket_type.quantity_available < num_tickets:
                    return Response(
                        {"error": f"Only {ticket_type.quantity_available} tickets available"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate total cost
                total_cost = ticket_type.price * num_tickets
                
                # Get user wallet
                try:
                    wallet = Wallet.objects.select_for_update().get(user=user)
                except Wallet.DoesNotExist:
                    return Response(
                        {"error": "User wallet not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate sufficient balance
                if wallet.balance < total_cost:
                    return Response(
                        {"error": f"Insufficient balance. Required: {total_cost}, Available: {wallet.balance}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Deduct wallet balance
                wallet.debit(
                    amount=total_cost,
                    description=f"Ticket purchase for {event.event_title}",
                    reference=f"TKT-{secrets.token_hex(8)}"
                )
                
                # Create issued tickets with unique QR codes
                issued_tickets = []
                for attendee in attendees:
                    # Generate cryptographically secure unique QR code
                    qr_code = f"QR-{secrets.token_urlsafe(32)}"
                    
                    ticket = IssuedTicket.objects.create(
                        ticket_type=ticket_type,
                        event=event,
                        owner_name=attendee['name'],
                        owner_email=attendee['email'],
                        purchased_by=user,
                        qr_code=qr_code,
                        status='unused'
                    )
                    issued_tickets.append(ticket)
                
                # Atomically reduce ticket quantity
                ticket_type.quantity_available -= num_tickets
                ticket_type.save()
                
                logger.info(
                    f"User {user.id} purchased {num_tickets} tickets for event {event.id}"
                )
        
        except TicketType.DoesNotExist:
            return Response(
                {"error": "Ticket type not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Ticket purchase failed: {str(e)}")
            return Response(
                {"error": "Ticket purchase failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Return issued tickets
        response_serializer = IssuedTicketSerializer(issued_tickets, many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class MyTicketsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my tickets",
        description="Retrieve all tickets purchased by or assigned to the authenticated user",
        responses={200: IssuedTicketSerializer(many=True)},
        tags=['Ticketing']
    )
    def get(self, request):
        user = request.user
        
        # Get tickets purchased by user or assigned to user's email
        tickets = IssuedTicket.objects.filter(
            purchased_by=user
        ) | IssuedTicket.objects.filter(
            owner_email=user.email
        )
        
        tickets = tickets.select_related('ticket_type', 'event').order_by('-created_at')
        
        serializer = IssuedTicketSerializer(tickets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ScanTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Scan ticket",
        description="Scan and validate a ticket. Only assigned event scanners can perform this action.",
        request=ScanTicketSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        tags=['Ticketing']
    )
    def post(self, request):
        serializer = ScanTicketSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        qr_code = serializer.validated_data['qr_code']
        event_id = serializer.validated_data['event_id']
        user = request.user
        
        # Check if user is an assigned scanner for this event
        is_scanner = EventScanner.objects.filter(
            user=user,
            event_id=event_id
        ).exists()
        
        if not is_scanner and not user.is_staff:
            return Response(
                {"error": "You are not authorized to scan tickets for this event"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            with transaction.atomic():
                # Get ticket with lock to prevent concurrent scans
                ticket = IssuedTicket.objects.select_for_update().get(qr_code=qr_code)
                
                # Validate ticket belongs to the event
                if str(ticket.event.id) != str(event_id):
                    return Response(
                        {"error": "Ticket does not belong to this event"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if ticket is already used
                if ticket.status == 'used':
                    return Response(
                        {
                            "error": "Ticket has already been used",
                            "ticket_owner": ticket.owner_name,
                            "ticket_email": ticket.owner_email,
                            "scan_time": ticket.created_at
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Mark ticket as used
                ticket.status = 'used'
                ticket.save()
                
                logger.info(
                    f"Ticket {ticket.id} scanned by user {user.id} for event {event_id}"
                )
                
                return Response(
                    {
                        "success": True,
                        "message": "Ticket validated successfully",
                        "ticket_owner": ticket.owner_name,
                        "ticket_email": ticket.owner_email,
                        "ticket_type": ticket.ticket_type.name,
                        "event_title": ticket.event.event_title,
                        "scan_time": timezone.now()
                    },
                    status=status.HTTP_200_OK
                )
        
        except IssuedTicket.DoesNotExist:
            return Response(
                {"error": "Invalid QR code"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Ticket scan failed: {str(e)}")
            return Response(
                {"error": "Ticket scan failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportAttendeesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export attendees",
        description="Export attendee list for an event. Only event owner or admin can access. Format: csv or txt",
        parameters=[
            OpenApiParameter(name='event_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH),
            OpenApiParameter(name='format', type=str, location=OpenApiParameter.QUERY, description='Export format: csv or txt')
        ],
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=['Ticketing']
    )
    def get(self, request, event_id):
        user = request.user
        export_format = request.query_params.get('format', 'csv').lower()
        
        # Get event
        event = get_object_or_404(EventInfo, id=event_id)
        
        # Check permissions: must be admin or event owner
        is_owner = event.vendor.id == request.query_params.get('vendor_id')
        is_admin = user.is_staff
        
        if not (is_admin or is_owner):
            return Response(
                {"error": "You do not have permission to export attendees for this event"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all tickets for this event
        tickets = IssuedTicket.objects.filter(event=event).select_related('ticket_type')
        
        if export_format == 'csv':
            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="attendees_{event.event_title}_{timezone.now().strftime("%Y%m%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Name', 'Email', 'Ticket Type', 'Status', 'QR Code', 'Purchase Date'])
            
            for ticket in tickets:
                writer.writerow([
                    ticket.owner_name,
                    ticket.owner_email,
                    ticket.ticket_type.name,
                    ticket.status,
                    ticket.qr_code,
                    ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            return response
        
        elif export_format == 'txt':
            # Create TXT response
            response = HttpResponse(content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="attendees_{event.event_title}_{timezone.now().strftime("%Y%m%d")}.txt"'
            
            lines = []
            lines.append(f"Attendee List for: {event.event_title}")
            lines.append(f"Event Date: {event.event_date}")
            lines.append(f"Location: {event.event_location}")
            lines.append("=" * 80)
            lines.append("")
            
            for ticket in tickets:
                lines.append(f"Name: {ticket.owner_name}")
                lines.append(f"Email: {ticket.owner_email}")
                lines.append(f"Ticket Type: {ticket.ticket_type.name}")
                lines.append(f"Status: {ticket.status}")
                lines.append(f"QR Code: {ticket.qr_code}")
                lines.append(f"Purchase Date: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("-" * 80)
            
            response.write('\n'.join(lines))
            return response
        
        else:
            return Response(
                {"error": "Invalid format. Use 'csv' or 'txt'"},
                status=status.HTTP_400_BAD_REQUEST
            )