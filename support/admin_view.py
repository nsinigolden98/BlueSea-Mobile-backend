from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from support.models import SupportMessage, SupportTicket
from support.serializers import (
    AddMessageSerializer,
    AdminTicketSerializer,
    AdminTicketUpdateSerializer,
    SupportMessageSerializer,
)
from support.views import create_attachments


class IsSupportAdmin(IsAuthenticated):
    """Exposed admin gate: request.user.is_admin is True."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(
            getattr(request.user, "is_admin", False)
        )


def _broadcast_ticket_event(ticket_id, owner_id, event_type, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    event = {"type": event_type, "event_data": payload}
    async_to_sync(channel_layer.group_send)(f"support_ticket_{ticket_id}", event)
    owner_group = f"support_user_{owner_id}"
    async_to_sync(channel_layer.group_send)(owner_group, event)


@extend_schema_view(
    get=extend_schema(
        summary="List all support tickets (admin)",
        description="Retrieve all support tickets ordered by most recent. Includes full message threads and attachments. Requires request.user.is_admin.",
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                required=False,
                description="Filter by status (open, in_progress, resolved, closed).",
            ),
            OpenApiParameter(
                name="priority",
                type=str,
                required=False,
                description="Filter by priority (low, medium, high, urgent).",
            ),
            OpenApiParameter(
                name="search",
                type=str,
                required=False,
                description="Search subject, description, or user email/name.",
            ),
        ],
        responses={200: AdminTicketSerializer(many=True)},
        tags=["Support Admin"],
        examples=[
            OpenApiExample(
                "Ticket list",
                summary="All tickets ordered by time (most recent first)",
                value={
                    "tickets": [
                        {
                            "id": 1,
                            "subject": "Cannot withdraw funds",
                            "description": "Withdrawal fails with error 500.",
                            "status": "open",
                            "priority": "high",
                            "message_count": 3,
                            "created_at": "2026-09-10T10:00:00Z",
                            "updated_at": "2026-09-10T10:05:00Z",
                            "user_name": "John Doe",
                            "user_email": "john@example.com",
                            "messages": [
                                {
                                    "id": 1,
                                    "sender_name": "John Doe",
                                    "message": "Withdrawal fails with error 500.",
                                    "is_admin": False,
                                    "created_at": "2026-09-10T10:00:00Z",
                                    "attachments": [],
                                }
                            ],
                        }
                    ],
                },
                response_only=True,
            )
        ],
    )
)
class AdminTicketListView(APIView):
    permission_classes = (IsSupportAdmin,)

    def get(self, request):
        tickets = (
            SupportTicket.objects.all()
            .prefetch_related("messages__sender", "messages__attachments")
            .annotate(message_count=Count("messages"))
            .order_by("-created_at")
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            tickets = tickets.filter(status=status_filter)
        priority_filter = request.query_params.get("priority")
        if priority_filter:
            tickets = tickets.filter(priority=priority_filter)
        search = request.query_params.get("search")
        if search:
            tickets = tickets.filter(
                Q(subject__icontains=search)
                | Q(description__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__surname__icontains=search)
                | Q(user__other_names__icontains=search)
            )
        serializer = AdminTicketSerializer(
            tickets, many=True, context={"request": request}
        )
        return Response({"tickets": serializer.data}, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        summary="Get support ticket detail (admin)",
        description="Retrieve a single support ticket with its full message thread and attachments by ID. Requires request.user.is_admin.",
        responses={200: AdminTicketSerializer, 404: OpenApiTypes.OBJECT},
        tags=["Support Admin"],
        examples=[
            OpenApiExample(
                "Not found",
                summary="404 when ticket is missing",
                value={"error": "Ticket not found"},
                response_only=True,
                status_codes=["404"],
            )
        ],
    ),
    patch=extend_schema(
        summary="Update ticket status or priority (admin)",
        description="Update the status and/or priority of a support ticket. Accepts partial updates. Requires request.user.is_admin.",
        request=AdminTicketUpdateSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=["Support Admin"],
        examples=[
            OpenApiExample(
                "Update request",
                summary="Update ticket status and priority",
                value={"status": "in_progress", "priority": "urgent"},
                request_only=True,
            ),
            OpenApiExample(
                "Updated",
                summary="Ticket updated successfully",
                value={"success": True, "status": "in_progress", "priority": "urgent"},
                response_only=True,
            ),
        ],
    ),
)
class AdminTicketDetailView(APIView):
    permission_classes = (IsSupportAdmin,)

    def get(self, request, ticket_id):
        ticket = (
            SupportTicket.objects.filter(id=ticket_id)
            .prefetch_related("messages__sender", "messages__attachments")
            .annotate(message_count=Count("messages"))
            .first()
        )
        if ticket is None:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = AdminTicketSerializer(ticket, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            serializer = AdminTicketUpdateSerializer(
                data=request.data, partial=True
            )
            if serializer.is_valid():
                update_fields = []
                if "status" in serializer.validated_data:
                    ticket.status = serializer.validated_data["status"]
                    update_fields.append("status")
                if "priority" in serializer.validated_data:
                    ticket.priority = serializer.validated_data["priority"]
                    update_fields.append("priority")
                if not update_fields:
                    return Response(
                        {"error": "Provide status and/or priority."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                update_fields.append("updated_at")
                ticket.save(update_fields=update_fields)
                payload = {
                    "type": "ticket_update",
                    "ticket_id": ticket.id,
                    "status": ticket.status,
                    "priority": ticket.priority,
                }
                _broadcast_ticket_event(
                    ticket.id, ticket.user_id, "message_event", payload
                )
                return Response(
                    {
                        "success": True,
                        "status": ticket.status,
                        "priority": ticket.priority,
                    }
                )
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )


@extend_schema_view(
    post=extend_schema(
        summary="Reply to a support ticket (admin)",
        description=(
            "Append an admin message to any ticket. Optional `images` is an array "
            "of image files (multipart/form-data). Requires request.user.is_admin. "
            "The reply is also pushed live on ws/support/<ticket_id>/."
        ),
        request=AddMessageSerializer,
        responses={201: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=["Support Admin"],
        examples=[
            OpenApiExample(
                "Admin reply",
                summary="Reply with text and optional images",
                value={"message": "We are looking into this.", "images": []},
                request_only=True,
            ),
        ],
    )
)
class AdminTicketReplyView(APIView):
    permission_classes = (IsSupportAdmin,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.select_related("user").get(id=ticket_id)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = AddMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        message = SupportMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            message=serializer.validated_data["message"],
            is_admin=True,
        )
        images = request.FILES.getlist("images")
        if images:
            create_attachments(message, images)
        data = SupportMessageSerializer(message, context={"request": request}).data
        _broadcast_ticket_event(
            ticket.id,
            ticket.user_id,
            "message_event",
            {"type": "new_message", "ticket_id": ticket.id, "message": data},
        )
        return Response(
            {"success": True, "message": data}, status=status.HTTP_201_CREATED
        )
