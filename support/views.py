from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from .models import SupportTicket, SupportMessage
from .serializers import (
    SupportTicketSerializer,
    CreateTicketSerializer,
    AddMessageSerializer,
    SupportMessageSerializer,
    SupportTicketListResponse,
    CreateTicketResponse,
    AddMessageResponse,
)


class SupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List my support tickets",
        description="Retrieve all support tickets belonging to the authenticated user.",
        operation_id="support_tickets_list",
        responses={200: SupportTicketListResponse},
        tags=["Support"],
    )
    def get(self, request):
        tickets = SupportTicket.objects.filter(user=request.user).order_by(
            "-created_at"
        )
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(
            {"count": tickets.count(), "tickets": serializer.data},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Create a support ticket",
        description="Create a new support ticket with an initial message for the authenticated user.",
        operation_id="support_ticket_create",
        request=CreateTicketSerializer,
        responses={201: CreateTicketResponse, 400: OpenApiTypes.OBJECT},
        tags=["Support"],
    )
    def post(self, request):
        serializer = CreateTicketSerializer(data=request.data)
        if serializer.is_valid():
            ticket = serializer.save(user=request.user)
            # Create initial message
            SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=serializer.validated_data["description"],
            )
            return Response(
                {
                    "success": True,
                    "message": "Support ticket created successfully",
                    "ticket": SupportTicketSerializer(ticket).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class SupportTicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get support ticket detail",
        description="Retrieve a single support ticket with its message thread for the authenticated user.",
        operation_id="support_ticket_retrieve",
        responses={200: SupportTicketSerializer, 404: OpenApiTypes.OBJECT},
        tags=["Support"],
    )
    def get(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            serializer = SupportTicketSerializer(ticket)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Add a message to a support ticket",
        description="Append a message to an existing support ticket owned by the authenticated user.",
        operation_id="support_ticket_add_message",
        request=AddMessageSerializer,
        responses={
            201: AddMessageResponse,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=["Support"],
    )
    def post(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            serializer = AddMessageSerializer(data=request.data)
            if serializer.is_valid():
                message = SupportMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    message=serializer.validated_data["message"],
                )
                return Response(
                    {
                        "success": True,
                        "message": SupportMessageSerializer(message).data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )
