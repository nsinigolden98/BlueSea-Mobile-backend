from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
import secrets
import csv

from loyalty_market.models import (
    Reward, RedemptionTransaction, EventInfo, TicketType, 
    IssuedTicket, TicketVendor, EventScanner
)
from loyalty_market.serializers import (
    RewardSerializer, RedeemPointsSerializer, EventInfoSerializer,
    CreateEventSerializer, PurchaseTicketSerializer, IssuedTicketSerializer,
    ScanTicketSerializer, AttendeeExportSerializer
)
from wallet.models import Wallet
from bonus.models import BonusPoint
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

import logging

logger = logging.getLogger(__name__)


# ============= EXISTING REWARD VIEWS =============

class RewardListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all rewards",
        description="Get all available rewards in the loyalty marketplace",
        responses={200: RewardSerializer(many=True)},
        tags=['Loyalty Market']
    )
    def get(self, request):
        rewards = Reward.objects.all()
        serializer = RewardSerializer(rewards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RewardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get reward details",
        description="Retrieve details of a specific reward",
        parameters=[
            OpenApiParameter(name='reward_id', type=int, location=OpenApiParameter.PATH, description='Reward ID')
        ],
        responses={200: RewardSerializer, 404: OpenApiTypes.OBJECT},
        tags=['Loyalty Market']
    )
    def get(self, request, reward_id):
        try:
            reward = Reward.objects.get(id=reward_id)
        except Reward.DoesNotExist:
            logger.error(f"Reward with id {reward_id} not found.")
            return Response({"error": "Reward not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RewardSerializer(reward)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserPointsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get user points balance",
        description="Retrieve the authenticated user's total bonus points",
        responses={200: OpenApiTypes.OBJECT},
        tags=['Loyalty Market']
    )
    def get(self, request):
        user = request.user
        try:
            bonus_point = BonusPoint.objects.get(user=user)
            total_points = bonus_point.points
        except BonusPoint.DoesNotExist:
            total_points = 0

        return Response({"total_points": total_points}, status=status.HTTP_200_OK)


class AdminCreateRewardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create new reward (Admin)",
        description="Create a new reward in the loyalty marketplace (admin only)",
        request=RewardSerializer,
        responses={201: RewardSerializer, 400: OpenApiTypes.OBJECT},
        tags=['Loyalty Market']
    )
    def post(self, request):
        serializer = RewardSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Reward creation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RedeemPointsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Redeem points for reward",
        description="Redeem bonus points to claim a reward",
        request=RedeemPointsSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=['Loyalty Market']
    )
    def post(self, request):
        serializer = RedeemPointsSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        points = Reward.objects.get(id=request.data.get('reward_id')).points_cost
        # Implementation continues here...


# ============= TICKETING SYSTEM VIEWS =============

class CreateEventView(APIView):
    """
    POST /events/create/
    Only admin or verified vendors can create events.
    Events start as is_approved = False.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create a new event",
        description="Create a new event. Only admin or verified vendors can create events. Events require admin approval.",
        request=CreateEventSerializer,
        responses={201: EventInfoSerializer, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        tags=['Ticketing']
    )
    def post(self, request):
        # Check if user is admin or verified vendor
        is_admin = request.user.is_staff
        vendor_id = request.data.get('vendor_id')
        
        if not is_admin:
            # Check if vendor is verified
            try:
                vendor = TicketVendor.objects.get(id=vendor_id)
                if not vendor.is_verified:
                    return Response(
                        {"error": "Only verified vendors can create events"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except TicketVendor.DoesNotExist:
                return Response(
                    {"error": "Vendor not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = CreateEventSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                event = serializer.save()
                logger.info(f"Event '{event.event_name}' created by vendor {vendor_id}")
            
            response_serializer = EventInfoSerializer(event)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventListView(APIView):
    """
    GET /events/
    List only approved events with ticket types and prices.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all approved events",
        description="Get all approved events with ticket types and pricing information",
        responses={200: EventInfoSerializer(many=True)},
        tags=['Ticketing']
    )
    def get(self, request):
        # Only return approved events
        events = EventInfo.objects.filter(is_approved=True).prefetch_related('ticket_types')
        serializer = EventInfoSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EventDetailView(APIView):
    """
    GET /events/<event_id>/
    Return event details with available ticket types.
    """
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
    """
    POST /tickets/purchase/
    Purchase tickets for an event.
    - Authenticated users only
    - Max 5 attendees per purchase
    - Validates ticket availability
    - Deducts wallet balance
    - Generates unique QR codes
    - Atomically reduces ticket quantity
    """
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
                    description=f"Ticket purchase for {event.event_name}",
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
    """
    GET /tickets/my/
    Return all tickets purchased by or assigned to the user.
    """
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
    """
    POST /tickets/scan/
    Scan and validate tickets.
    - Only assigned EventScanner users can scan
    - Validates QR code and event
    - Marks ticket as used
    """
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
                        "event_name": ticket.event.event_name,
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
    """
    GET /events/<event_id>/attendees/export/
    Export attendee list for an event.
    - Only event owner or admin can access
    - Export as CSV or TXT
    """
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
            response['Content-Disposition'] = f'attachment; filename="attendees_{event.event_name}_{timezone.now().strftime("%Y%m%d")}.csv"'
            
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
            response['Content-Disposition'] = f'attachment; filename="attendees_{event.event_name}_{timezone.now().strftime("%Y%m%d")}.txt"'
            
            lines = []
            lines.append(f"Attendee List for: {event.event_name}")
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