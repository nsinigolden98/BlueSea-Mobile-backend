from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import render
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from support.models import SupportTicket
from support.serializers import AdminTicketSerializer, AdminTicketUpdateSerializer


@extend_schema_view(
    get=extend_schema(
        summary="List all support tickets (admin)",
        description="Retrieve all support tickets ordered by most recent. Includes full message threads and attachments. Staff only.",
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
    permission_classes = (IsAuthenticated,)
    def get(self, request):
        tickets = (
            SupportTicket.objects.filter()
            .prefetch_related("messages__sender", "messages__attachments")
            .annotate(message_count=Count("messages"))
            .order_by("-created_at")
        )
        serializer = AdminTicketSerializer(
            tickets, many=True, context={"request": request}
        )
        return Response({"tickets": serializer.data})


@extend_schema_view(
    get=extend_schema(
        summary="Get support ticket detail (admin)",
        description="Retrieve a single support ticket with its full message thread and attachments by ID. Staff only.",
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
        description="Update the status and/or priority of a support ticket. Accepts partial updates. Staff only.",
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
    permission_classes = (IsAuthenticated,)

    def get(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            serializer = AdminTicketSerializer(ticket, context={"request": request})
            return Response(serializer.data)
        except SupportTicket.DoesNotExist:
            return Response({"error": "Ticket not found"}, status=404)

    def patch(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            serializer = AdminTicketUpdateSerializer(data=request.data, partial=True)
            if serializer.is_valid():
                if "status" in serializer.validated_data:
                    ticket.status = serializer.validated_data["status"]
                if "priority" in serializer.validated_data:
                    ticket.priority = serializer.validated_data["priority"]
                ticket.save(update_fields=["status", "priority"])
                return Response(
                    {
                        "success": True,
                        "status": ticket.status,
                        "priority": ticket.priority,
                    }
                )
            return Response({"error": serializer.errors}, status=400)
        except SupportTicket.DoesNotExist:
            return Response({"error": "Ticket not found"}, status=404)


@staff_member_required
def admin_support(request):
    return render(request, "support/admin_support.html", {})
