from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import (
    EventInfoSerializer,
    CreateEventSerializer, PurchaseTicketSerializer, IssuedTicketSerializer,
    ScanTicketSerializer, AttendeeExportSerializer, TicketListSerializer, TicketDetailSerializer, TransferTicketSerializer, CancelTicketSerializer
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
from .utils import generate_ticket_qr_code, parse_qr_data
import uuid
import base64
from django.core.files.base import ContentFile
from rest_framework.throttling import UserRateThrottle
from accounts.models import Profile

logger = logging.getLogger(__name__)

# ============= TICKETING SYSTEM VIEWS =============

class CreateEventView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
            vendor = TicketVendor.objects.filter(user=user).first()
            vendor_id = vendor.id if vendor else None
            
            # Check if vendor exists and is verified
            try:
                if not vendor.is_verified:
                    return Response(
                        {"error": "Only verified vendors can create events. Please complete KYC verification."},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except TicketVendor.DoesNotExist:
                return Response({
                    'error': 'Vendor not found',
                    'state': False
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if is_free
        is_free = request.data.get('is_free', 'false')
        if isinstance(is_free, str):
            is_free = is_free.lower() in ['true', '1', 'yes']

        ticket_types_data = request.data.get('ticket_types', '[]')
        if isinstance(ticket_types_data, str):
            # It's a JSON string from form-data
            ticket_types_data = ticket_types_data.strip()
            
            if ticket_types_data in ['[]', '', 'null', 'None']:
                # Empty or null values
                ticket_types_data = []
            else:
                # Parse JSON string
                try:
                    import json
                    ticket_types_data = json.loads(ticket_types_data)
                    
                    # Ensure it's a list
                    if not isinstance(ticket_types_data, list):
                        return Response({
                            'error': 'ticket_types must be an array',
                            'state': False
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                except json.JSONDecodeError as e:
                    return Response({
                        'error': f'Invalid ticket_types JSON format: {str(e)}',
                        'state': False
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        elif isinstance(ticket_types_data, list):
            # Already a list (from JSON request body)
            pass
        
        else:
            # Unknown type
            ticket_types_data = []
        
        # For free events, ensure ticket_types is empty
        if is_free:
            ticket_types_data = []
        
        # Log for debugging
        logger.debug(f"Parsed ticket_types: {ticket_types_data}")
        logger.debug(f"ticket_types type: {type(ticket_types_data)}")
        if ticket_types_data:
            logger.debug(f"First item type: {type(ticket_types_data[0])}")
        
        # Prepare data for serializer
        event_data = {
            'vendor': vendor.id,
            'event_title': request.data.get('event_title'),
            'event_description': request.data.get('event_description'),
            'event_date': request.data.get('event_date'),
            'event_location': request.data.get('event_location'),
            'hosted_by': request.data.get('hosted_by'),
            'category': request.data.get('category'),
            'is_free': is_free,
            'event_banner': request.data.get('event_banner'),
            'ticket_image': request.data.get('ticket_image'),
            'ticket_types': ticket_types_data  # Already parsed as list of dicts
        }
        
        # Create event
        serializer = CreateEventSerializer(data=event_data)
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    event = serializer.save()
                    logger.info(
                        f"Event '{event.event_title}' created by user {request.user.id}. "
                        f"Hosted by: {event.hosted_by}, Category: {event.category}, "
                        f"Vendor: {event.vendor.brand_name}, Free: {event.is_free}"
                    )
                
                # Return complete event details with ticket types
                response_serializer = EventInfoSerializer(event, context={'request': request})
                return Response({
                    'success': True,
                    'message': 'Event created successfully and pending approval',
                    'event': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                logger.error(f"Event creation failed: {str(e)}")
                return Response({
                    'error': f"Failed to create event: {str(e)}",
                    'state': False
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
        description="Purchase tickets for an event. Provide ticket type name (e.g., 'Regular', 'VIP'). Leave empty for free events.",
        parameters=[
            OpenApiParameter(name='event_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH, description='Event ID')
        ],
        request=PurchaseTicketSerializer,
        responses={
            201: IssuedTicketSerializer(many=True),
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Ticketing']
    )
    def post(self, request, event_id):
        """Purchase tickets for a specific event"""
        # Pass event_id to serializer context
        serializer = PurchaseTicketSerializer(
            data=request.data, 
            context={'request': request, 'event_id': event_id}
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        event = serializer.validated_data['event_obj']
        ticket_type_obj = serializer.validated_data.get('ticket_type_obj')
        quantity = serializer.validated_data['quantity']
        attendees = serializer.validated_data['attendees']
        transaction_pin = serializer.validated_data.get('transaction_pin')

        # Check if event is approved
        if not event.is_approved:
            return Response({
                'error': 'This event is not yet approved for ticket sales',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if event date has passed
        if event.event_date < timezone.now():
            return Response({
                'error': 'This event has already passed',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Handle FREE events
        if event.is_free:
            if ticket_type_obj:
                return Response({
                    'error': 'Free events do not have ticket types',
                    'state': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                with transaction.atomic():
                    issued_tickets = []
                    
                    for attendee in attendees:
                        ticket = IssuedTicket.objects.create(
                            event=event,
                            ticket_type=None,
                            purchased_by=request.user,
                            owner_name=attendee['name'],
                            owner_email=attendee['email'],
                            qr_code='',
                            status='upcoming'
                        )
                        
                        # Generate QR code
                        qr_data = f"{str(ticket.id)}:free-ticket:{attendee['email']}"
                        ticket.qr_code = qr_data
                        ticket.save()
                        
                        # Generate QR image
                        try:
                            qr_code_image = generate_ticket_qr_code(ticket)
                        except Exception as qr_error:
                            logger.warning(f"QR code image generation failed: {str(qr_error)}")
                        
                        issued_tickets.append(ticket)
                    
                    logger.info(
                        f"User {request.user.email} registered {quantity} free ticket(s) for '{event.event_title}'"
                    )
                    
                    return Response({
                        'success': True,
                        'message': f'{quantity} free ticket(s) registered successfully for {event.event_title}',
                        'tickets': IssuedTicketSerializer(issued_tickets, many=True, context={'request': request}).data,
                        'total_cost': '0.00'
                    }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                logger.error(f"Free ticket creation failed: {str(e)}", exc_info=True)
                return Response({
                    'error': f"Failed to register free tickets: {str(e)}",
                    'state': False
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Handle PAID events
        ticket_type = ticket_type_obj
        
        if not transaction_pin:
            return Response({
                'error': 'Transaction PIN is required for paid events',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check ticket availability
        if ticket_type.quantity_available < quantity:
            return Response({
                'error': f'Only {ticket_type.quantity_available} tickets available for {ticket_type.name}',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calculate total cost
        total_cost = ticket_type.price * quantity

        # Get user wallet
        try:
            wallet = Wallet.objects.get(user=request.user)
        except Wallet.DoesNotExist:
            return Response({
                'error': 'Wallet not found. Please contact support.',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # try:
        #     user_profile = Profile.objects.get(user=request.user)
        # except Profile.DoesNotExist:
        #     return Response({
        #         'error': 'User profile not found. Please contact support.',
        #         'state': False
        #     }, status=status.HTTP_404_NOT_FOUND)

        # Verify transaction PIN
        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({
                'error': 'Invalid transaction PIN',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check sufficient balance
        if wallet.balance < total_cost:
            return Response({
                'error': f'Insufficient balance. Required: ₦{total_cost:,.2f}, Available: ₦{wallet.balance:,.2f}',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Process payment and issue tickets
        try:
            with transaction.atomic():
                # Deduct from wallet
                wallet.balance -= total_cost
                wallet.save()

                # Reduce ticket quantity
                ticket_type.quantity_available -= quantity
                ticket_type.save()

                # Create tickets
                issued_tickets = []
                for attendee in attendees:
                    ticket = IssuedTicket.objects.create(
                        event=event,
                        ticket_type=ticket_type,
                        purchased_by=request.user,
                        owner_name=attendee['name'],
                        owner_email=attendee['email'],
                        qr_code='',
                        status='upcoming'
                    )
                    
                    # Generate QR code
                    qr_data = f"{str(ticket.id)}:{str(ticket_type.id)}:{attendee['email']}"
                    ticket.qr_code = qr_data
                    ticket.save()
                    
                    # Generate QR image
                    try:
                        qr_code_image = generate_ticket_qr_code(ticket)
                    except Exception as qr_error:
                        logger.warning(f"QR code image generation failed: {str(qr_error)}")
                    
                    issued_tickets.append(ticket)

                # Award bonus points (1% of total cost)
                # bonus_points = int(total_cost * Decimal('0.01'))
                # if bonus_points > 0:
                #     BonusPoint.objects.create(
                #         user=request.user,
                #         points=bonus_points,
                #         transaction_type='ticket_purchase',
                #         description=f'Bonus for purchasing {quantity} ticket(s) for {event.event_title}'
                #     )

                # logger.info(
                #     f"User {request.user.id} purchased {quantity} ticket(s) for event '{event.event_title}'. "
                #     f"Total: ₦{total_cost}, Bonus: {bonus_points} points"
                # )

                return Response({
                    'success': True,
                    'message': f'{quantity} {ticket_type.name} ticket(s) purchased successfully for {event.event_title}',
                    'tickets': IssuedTicketSerializer(issued_tickets, many=True, context={'request': request}).data,
                    'total_cost': str(total_cost),
                    'wallet_balance': str(wallet.balance),
                    # 'bonus_points_earned': bonus_points
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Ticket purchase failed: {str(e)}", exc_info=True)
            return Response({
                'error': f"Transaction failed: {str(e)}",
                'state': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


class ScannerRateThrottle(UserRateThrottle):
    """Custom throttle for ticket scanning - 20 scans per minute"""
    rate = '20/min'


class ScanTicketView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScannerRateThrottle]
    
    @extend_schema(
        summary="Scan and validate ticket QR code",
        description="Scan a ticket QR code to validate and mark as used. Requires scanner assignment or staff access.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'qr_data': {'type': 'string', 'description': 'QR code data from scanner'},
                    'event_id': {'type': 'string', 'format': 'uuid', 'description': 'Event UUID being scanned for'}
                },
                'required': ['qr_data', 'event_id']
            }
        },
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=['Marketplace']
    )
    def post(self, request):
        qr_data = request.data.get('qr_data')
        # event_id = request.data.get('event_id')
        
        if not qr_data:
            return Response({
                'error': 'qr_data is required',
                'state': False,
                'error_code': 'MISSING_PARAMETERS'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        ticket_uuid, event_uuid, is_valid = parse_qr_data(qr_data)
        
        # Verify event exists and is approved
        try:
            event = EventInfo.objects.get(id=event_uuid, is_approved=True)
        except EventInfo.DoesNotExist:
            return Response({
                'error': 'Event not found or not approved',
                'state': False,
                'error_code': 'INVALID_EVENT'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check scanner authorization
        is_authorized = (
            request.user.is_staff or 
            EventScanner.objects.filter(user=request.user, event=event).exists() or
            event.vendor.user == request.user  # Vendor can scan their own events
        )
        
        if not is_authorized:
            return Response({
                'error': 'You are not authorized to scan tickets for this event',
                'state': False,
                'error_code': 'UNAUTHORIZED_SCANNER'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Parse and verify QR code
        ticket_uuid, qr_event_uuid, is_valid = parse_qr_data(qr_data)
        
        if not is_valid:
            return Response({
                'error': 'Invalid or tampered QR code',
                'state': False,
                'error_code': 'INVALID_QR_CODE',
                'scan_result': 'rejected'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify event UUID matches
        if str(event.id) != qr_event_uuid:
            return Response({
                'error': 'QR code is for a different event',
                'state': False,
                'error_code': 'EVENT_MISMATCH',
                'scan_result': 'rejected'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get ticket with lock to prevent race conditions
        try:
            with transaction.atomic():
                ticket = IssuedTicket.objects.select_for_update().select_related(
                    'event', 'ticket_type', 'purchased_by', 'scanned_by'
                ).get(id=ticket_uuid)
                
                # Validate ticket status
                if ticket.status == 'used':
                    # Show who scanned it and when
                    scanned_by_info = {
                        'email': ticket.scanned_by.email if ticket.scanned_by else 'Unknown',
                        'time': ticket.scanned_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.scanned_at else 'Unknown'
                    }
                    return Response({
                        'error': 'Ticket has already been used',
                        'state': False,
                        'error_code': 'ALREADY_USED',
                        'scan_result': 'rejected',
                        'ticket_details': {
                            'ticket_id': str(ticket.id),
                            'owner_name': ticket.owner_name,
                            'owner_email': ticket.owner_email,
                            'status': ticket.status,
                            'scanned_by': scanned_by_info['email'],
                            'scanned_at': scanned_by_info['time']
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if ticket.status == 'expired':
                    return Response({
                        'error': 'Ticket has expired',
                        'state': False,
                        'error_code': 'EXPIRED',
                        'scan_result': 'rejected',
                        'ticket_details': {
                            'ticket_id': str(ticket.id),
                            'owner_name': ticket.owner_name,
                            'status': ticket.status
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if ticket.status == 'transferred':
                    return Response({
                        'error': 'Ticket has been transferred to another user',
                        'state': False,
                        'error_code': 'TRANSFERRED',
                        'scan_result': 'rejected',
                        'ticket_details': {
                            'ticket_id': str(ticket.id),
                            'transferred_to': ticket.transferred_to,
                            'transferred_at': ticket.transferred_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.transferred_at else None
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if ticket.status == 'canceled':
                    return Response({
                        'error': 'Ticket has been canceled',
                        'state': False,
                        'error_code': 'CANCELED',
                        'scan_result': 'rejected',
                        'ticket_details': {
                            'ticket_id': str(ticket.id),
                            'canceled_at': ticket.canceled_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.canceled_at else None
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Optional: Validate event time (allow scanning 2 hours before event)
                time_until_event = ticket.event.event_date - timezone.now()
                if time_until_event.total_seconds() > 2 * 3600:  # 2 hours in seconds
                    hours_remaining = int(time_until_event.total_seconds() / 3600)
                    return Response({
                        'error': f'Event starts in {hours_remaining} hours. Early entry not allowed yet.',
                        'state': False,
                        'error_code': 'TOO_EARLY',
                        'scan_result': 'rejected',
                        'event_start': ticket.event.event_date.strftime('%Y-%m-%d %H:%M:%S')
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Mark ticket as used
                ticket.status = 'used'
                ticket.scanned_at = timezone.now()
                ticket.scanned_by = request.user
                ticket.save()
                
                # Build successful response with full ticket details
                return Response({
                    'message': 'Ticket validated successfully',
                    'state': True,
                    'scan_result': 'success',
                    'ticket_details': {
                        'ticket_id': str(ticket.id),
                        'owner_name': ticket.owner_name,
                        'owner_email': ticket.owner_email,
                        'ticket_type': {
                            'name': ticket.ticket_type.name,
                            'price': float(ticket.ticket_type.price)
                        },
                        'event': {
                            'title': ticket.event.event_title,
                            'date': ticket.event.event_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'location': ticket.event.event_location,
                            'vendor': ticket.event.vendor.brand_name
                        },
                        'purchased_by': ticket.purchased_by.email if ticket.purchased_by else None,
                        'status': ticket.status,
                        'scanned_at': ticket.scanned_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'scanned_by': request.user.email
                    }
                }, status=status.HTTP_200_OK)
                
        except IssuedTicket.DoesNotExist:
            return Response({
                'error': 'Ticket not found',
                'state': False,
                'error_code': 'TICKET_NOT_FOUND',
                'scan_result': 'rejected'
            }, status=status.HTTP_404_NOT_FOUND)


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


class TicketListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get all tickets owned by current user",
        description="Retrieve all tickets that YOU CURRENTLY OWN (including transferred to you). Filter by status.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter tickets by status',
                enum=['all', 'upcoming', 'used', 'expired', 'canceled']
            )
        ],
        responses={200: TicketListSerializer(many=True)},
        tags=['Ticketing']
    )
    def get(self, request):
        """Get all tickets owned by the current user (by owner_email, not purchaser)"""
        status_filter = request.query_params.get('status', 'all')
        
        # Get tickets where the user is the CURRENT OWNER (not original purchaser)
        tickets = IssuedTicket.objects.filter(
            owner_email=request.user.email
        ).select_related('event', 'ticket_type', 'event__vendor')
        
        # Apply status filter
        if status_filter != 'all':
            tickets = tickets.filter(status=status_filter)
        
        serializer = TicketListSerializer(
            tickets, 
            many=True, 
            context={'request': request}
        )
        
        return Response({
            'state': True,
            'count': tickets.count(),
            'tickets': serializer.data
        }, status=status.HTTP_200_OK)


class TicketDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get ticket details",
        description="Retrieve detailed information for a specific ticket including QR code",
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=['Marketplace']
    )
    def get(self, request, ticket_id):
        try:
            ticket = IssuedTicket.objects.select_related(
                'event', 'ticket_type', 'event__vendor', 'purchased_by', 'scanned_by'
            ).get(id=ticket_id, purchased_by=request.user)
            
            from .serializers import TicketDetailSerializer
            serializer = TicketDetailSerializer(ticket)
            
            return Response({
                'state': True,
                'ticket': serializer.data
            }, status=status.HTTP_200_OK)
            
        except IssuedTicket.DoesNotExist:
            return Response({
                'error': 'Ticket not found',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)


class MyTicketsListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my tickets with statistics",
        description="Get all tickets you currently own with grouped statistics",
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by status',
                enum=['all', 'upcoming', 'used', 'expired', 'canceled']
            )
        ],
        responses={200: TicketListSerializer(many=True)},
        tags=['Ticketing']
    )
    def get(self, request):
        """Get tickets owned by current user with stats"""
        status_filter = request.query_params.get('status', 'all')
        
        # Base queryset - tickets where user is CURRENT OWNER
        base_tickets = IssuedTicket.objects.filter(
            owner_email=request.user.email
        ).select_related('event', 'ticket_type', 'event__vendor')
        
        # Calculate statistics
        stats = {
            'all': base_tickets.count(),
            'upcoming': base_tickets.filter(status='upcoming').count(),
            'used': base_tickets.filter(status='used').count(),
            'expired': base_tickets.filter(status='expired').count(),
            'canceled': base_tickets.filter(status='canceled').count(),
        }
        
        # Filter by status
        if status_filter != 'all':
            tickets = base_tickets.filter(status=status_filter)
        else:
            tickets = base_tickets
        
        serializer = TicketListSerializer(
            tickets,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'state': True,
            'stats': stats,
            'tickets': serializer.data
        }, status=status.HTTP_200_OK)


class TicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get single ticket details",
        description="Get detailed information about a specific ticket you own",
        responses={
            200: TicketDetailSerializer,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Ticketing']
    )
    def get(self, request, ticket_id):
        """Get single ticket details - only if you're the current owner"""
        try:
            ticket = IssuedTicket.objects.select_related(
                'event', 'ticket_type', 'purchased_by', 'scanned_by'
            ).get(id=ticket_id)
        except IssuedTicket.DoesNotExist:
            return Response({
                'error': 'Ticket not found',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is the CURRENT OWNER (not original purchaser)
        if ticket.owner_email != request.user.email:
            return Response({
                'error': 'You do not own this ticket',
                'state': False
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = TicketDetailSerializer(ticket, context={'request': request})
        
        return Response({
            'state': True,
            'ticket': serializer.data
        }, status=status.HTTP_200_OK)


class TransferTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Transfer ticket to another person",
        description="Transfer your ticket to another person. Tickets can only be transferred once and not within 6 hours of event.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'recipient_email': {'type': 'string', 'format': 'email'},
                    'recipient_name': {'type': 'string'}
                },
                'required': ['recipient_email', 'recipient_name']
            }
        },
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Ticketing']
    )
    def post(self, request, ticket_id):
        """Transfer a ticket to another person"""
        recipient_email = request.data.get('recipient_email')
        recipient_name = request.data.get('recipient_name')
        
        if not recipient_email or not recipient_name:
            return Response({
                'error': 'recipient_email and recipient_name are required',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Don't allow transferring to yourself
        if recipient_email.lower() == request.user.email.lower():
            return Response({
                'error': 'You cannot transfer a ticket to yourself',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get ticket
        try:
            ticket = IssuedTicket.objects.get(id=ticket_id)
        except IssuedTicket.DoesNotExist:
            return Response({
                'error': 'Ticket not found',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if current user is the CURRENT OWNER (not original purchaser)
        if ticket.owner_email != request.user.email:
            return Response({
                'error': 'You do not own this ticket. Only the current owner can transfer it.',
                'state': False
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if ticket can be transferred
        can_transfer, message = ticket.can_transfer()
        if not can_transfer:
            return Response({
                'error': message,
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Transfer ticket - ownership changes completely
        try:
            with transaction.atomic():
                # Store previous owner info for logging
                previous_owner = ticket.owner_email
                
                # Transfer ownership
                ticket.owner_name = recipient_name
                ticket.owner_email = recipient_email
                ticket.transferred_to = recipient_email
                ticket.transferred_at = timezone.now()
                ticket.transfer_count += 1
                ticket.status = 'upcoming'  # Keep as upcoming, not "transferred"
                ticket.save()
                
                logger.info(
                    f"Ticket {ticket.id} transferred from {previous_owner} to {recipient_email}. "
                    f"Event: {ticket.event.event_title}"
                )
                
                return Response({
                    'message': f'Ticket successfully transferred to {recipient_email}. You no longer own this ticket.',
                    'state': True,
                    'ticket_id': str(ticket.id),
                    'transferred_to': f"{recipient_name} ({recipient_email})",
                    'transferred_at': ticket.transferred_at,
                    'previous_owner': previous_owner
                }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Ticket transfer failed: {str(e)}")
            return Response({
                'error': f"Transfer failed: {str(e)}",
                'state': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cancel ticket and get refund",
        description="Cancel your ticket and receive a refund based on cancellation policy. Refund depends on time before event.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reason': {'type': 'string'},
                    'transaction_pin': {'type': 'string', 'minLength': 4, 'maxLength': 6}
                },
                'required': ['reason', 'transaction_pin']
            }
        },
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Ticketing']
    )
    def post(self, request, ticket_id):
        """Cancel a ticket and process refund"""
        reason = request.data.get('reason')
        transaction_pin = request.data.get('transaction_pin')
        
        if not reason:
            return Response({
                'error': 'Cancellation reason is required',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get ticket
        try:
            ticket = IssuedTicket.objects.get(id=ticket_id)
        except IssuedTicket.DoesNotExist:
            return Response({
                'error': 'Ticket not found',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check ownership
        if ticket.purchased_by != request.user:
            return Response({
                'error': 'You do not have permission to cancel this ticket',
                'state': False
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if ticket can be canceled
        can_cancel, refund_amount, message = ticket.can_cancel()
        if not can_cancel:
            return Response({
                'error': message,
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For paid tickets, verify transaction PIN
        if ticket.ticket_type and not ticket.event.is_free:
            if not transaction_pin:
                return Response({
                    'error': 'Transaction PIN is required for paid ticket cancellations',
                    'state': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user wallet
            try:
                wallet = Wallet.objects.get(user=request.user)
            except Wallet.DoesNotExist:
                return Response({
                    'error': 'Wallet not found',
                    'state': False
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Verify PIN - request.user IS the Profile, no need for Profile.objects.get()
            if not request.user.verify_transaction_pin(transaction_pin):
                return Response({
                    'error': 'Invalid transaction PIN',
                    'state': False
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process cancellation
        try:
            with transaction.atomic():
                # Update ticket status
                ticket.status = 'canceled'
                ticket.canceled_at = timezone.now()
                ticket.cancellation_reason = reason
                ticket.refund_amount = refund_amount
                ticket.save()
                
                # Process refund for paid tickets
                if refund_amount > 0 and ticket.ticket_type:
                    wallet.balance += refund_amount
                    wallet.save()
                    
                    # Restore ticket quantity
                    ticket.ticket_type.quantity_available += 1
                    ticket.ticket_type.save()
                    
                    logger.info(
                        f"Ticket {ticket.id} canceled. Refund: ₦{refund_amount} credited to user {request.user.id}"
                    )
                    
                    return Response({
                        'message': 'Ticket canceled successfully',
                        'state': True,
                        'refund_amount': str(refund_amount),
                        'refund_policy': message,
                        'ticket_id': str(ticket.id),
                        'canceled_at': ticket.canceled_at,
                        'wallet_balance': str(wallet.balance)
                    }, status=status.HTTP_200_OK)
                else:
                    # Free ticket cancellation (no refund)
                    logger.info(f"Free ticket {ticket.id} canceled by user {request.user.id}")
                    
                    return Response({
                        'message': 'Free ticket canceled successfully',
                        'state': True,
                        'ticket_id': str(ticket.id),
                        'canceled_at': ticket.canceled_at
                    }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Ticket cancellation failed: {str(e)}")
            return Response({
                'error': f"Cancellation failed: {str(e)}",
                'state': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ScannerDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get scanner dashboard statistics",
        description="Retrieve scan statistics for a specific event including total tickets, scanned count, and recent scans",
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=['Marketplace']
    )
    def get(self, request, event_id):
        try:
            event = EventInfo.objects.get(id=event_id, is_approved=True)
        except EventInfo.DoesNotExist:
            return Response({
                'error': 'Event not found or not approved',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check authorization
        is_authorized = (
            request.user.is_staff or 
            EventScanner.objects.filter(user=request.user, event=event).exists() or
            event.vendor.user == request.user
        )
        
        if not is_authorized:
            return Response({
                'error': 'You are not authorized to view this event\'s dashboard',
                'state': False
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get statistics
        all_tickets = IssuedTicket.objects.filter(event=event)
        total_issued = all_tickets.count()
        total_scanned = all_tickets.filter(status='used').count()
        total_remaining = all_tickets.filter(status='upcoming').count()
        total_expired = all_tickets.filter(status='expired').count()
        total_canceled = all_tickets.filter(status='canceled').count()
        
        # Get scanner's personal scan count
        personal_scans = all_tickets.filter(scanned_by=request.user).count()
        
        # Get recent scans (last 20)
        recent_scans = IssuedTicket.objects.filter(
            event=event,
            status='used'
        ).select_related('scanned_by', 'ticket_type').order_by('-scanned_at')[:20]
        
        recent_scans_data = [
            {
                'ticket_id': str(scan.id)[:8],
                'owner_name': scan.owner_name,
                'ticket_type': scan.ticket_type.name,
                'scanned_at': scan.scanned_at.strftime('%Y-%m-%d %H:%M:%S'),
                'scanned_by': scan.scanned_by.email if scan.scanned_by else 'Unknown'
            }
            for scan in recent_scans
        ]
        
        return Response({
            'state': True,
            'event': {
                'id': str(event.id),
                'title': event.event_title,
                'date': event.event_date.strftime('%Y-%m-%d %H:%M:%S'),
                'location': event.event_location,
                'vendor': event.vendor.brand_name
            },
            'statistics': {
                'total_issued': total_issued,
                'total_scanned': total_scanned,
                'total_remaining': total_remaining,
                'total_expired': total_expired,
                'total_canceled': total_canceled,
                'scan_percentage': round((total_scanned / total_issued * 100) if total_issued > 0 else 0, 2)
            },
            'personal_stats': {
                'scans_by_you': personal_scans,
                'percentage_of_total': round((personal_scans / total_scanned * 100) if total_scanned > 0 else 0, 2)
            },
            'recent_scans': recent_scans_data
        }, status=status.HTTP_200_OK)




class MyScannerAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get my scanner assignments",
        description="Retrieve all events the authenticated user is assigned to scan",
        responses={200: OpenApiTypes.OBJECT},
        tags=['Marketplace']
    )
    def get(self, request):
        # Get events user is assigned to scan
        assignments = EventScanner.objects.filter(
            user=request.user
        ).select_related('event', 'event__vendor')
        
        # Also include events owned by user's vendor account
        vendor_events = []
        try:
            vendor = TicketVendor.objects.get(user=request.user)
            vendor_events = EventInfo.objects.filter(vendor=vendor, is_approved=True)
        except TicketVendor.DoesNotExist:
            pass
        
        # Build response
        assigned_events = []
        
        for assignment in assignments:
            event = assignment.event
            if not event.is_approved:
                continue
            
            # Get stats for this event
            total_tickets = IssuedTicket.objects.filter(event=event).count()
            scanned_tickets = IssuedTicket.objects.filter(event=event, status='used').count()
            
            assigned_events.append({
                'event_id': str(event.id),
                'event_title': event.event_title,
                'event_date': event.event_date.strftime('%Y-%m-%d %H:%M:%S'),
                'event_location': event.event_location,
                'event_banner': request.build_absolute_uri(event.event_banner.url) if event.event_banner else None,
                'vendor': event.vendor.brand_name,
                'role': 'scanner',
                'statistics': {
                    'total_tickets': total_tickets,
                    'scanned_tickets': scanned_tickets,
                    'remaining': total_tickets - scanned_tickets
                },
                'assigned_at': assignment.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Add vendor's own events
        for event in vendor_events:
            total_tickets = IssuedTicket.objects.filter(event=event).count()
            scanned_tickets = IssuedTicket.objects.filter(event=event, status='used').count()
            
            assigned_events.append({
                'event_id': str(event.id),
                'event_title': event.event_title,
                'event_date': event.event_date.strftime('%Y-%m-%d %H:%M:%S'),
                'event_location': event.event_location,
                'event_banner': request.build_absolute_uri(event.event_banner.url) if event.event_banner else None,
                'vendor': event.vendor.brand_name,
                'role': 'vendor',
                'statistics': {
                    'total_tickets': total_tickets,
                    'scanned_tickets': scanned_tickets,
                    'remaining': total_tickets - scanned_tickets
                }
            })
        
        return Response({
            'state': True,
            'count': len(assigned_events),
            'events': assigned_events
        }, status=status.HTTP_200_OK)


class AddEventScannerView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Add scanner to event",
        description="Assign a user as scanner for your event (vendor only)",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_email': {'type': 'string', 'format': 'email'},
                },
                'required': ['user_email']
            }
        },
        responses={201: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        tags=['Marketplace']
    )
    def post(self, request, event_id):
        user_email = request.data.get('user_email')
        
        if not user_email:
            return Response({
                'error': 'user_email is required',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            event = EventInfo.objects.get(id=event_id)
        except EventInfo.DoesNotExist:
            return Response({
                'error': 'Event not found',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify user is vendor and owns this event
        try:
            vendor = TicketVendor.objects.get(user=request.user)
            if event.vendor != vendor:
                return Response({
                    'error': 'You can only add scanners to your own events',
                    'state': False
                }, status=status.HTTP_403_FORBIDDEN)
        except TicketVendor.DoesNotExist:
            return Response({
                'error': 'Only vendors can add scanners',
                'state': False
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get user to assign
        try:
            from accounts.models import Profile
            scanner_user = Profile.objects.get(email=user_email)
        except Profile.DoesNotExist:
            return Response({
                'error': 'User with this email not found',
                'state': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already assigned
        if EventScanner.objects.filter(user=scanner_user, event=event).exists():
            return Response({
                'error': 'User is already assigned as scanner for this event',
                'state': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create scanner assignment
        scanner = EventScanner.objects.create(
            user=scanner_user,
            event=event
        )
        
        # TODO: Send notification to scanner
        # send_scanner_assignment_notification(scanner_user, event)
        
        return Response({
            'message': f'{scanner_user.email} added as scanner for {event.event_title}',
            'state': True,
            'scanner': {
                'email': scanner_user.email,
                'event': event.event_title,
                'assigned_at': scanner.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        }, status=status.HTTP_201_CREATED)