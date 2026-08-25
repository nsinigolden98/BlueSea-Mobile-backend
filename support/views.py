from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import SupportTicket, SupportMessage, SupportAttachment
from .serializers import (
    SupportTicketSerializer,
    CreateTicketSerializer,
    AddMessageSerializer,
    SupportMessageSerializer,
    SupportTicketListResponse,
    CreateTicketResponse,
    AddMessageResponse,
)


def create_attachments(message, images):
    for image in images:
        SupportAttachment.objects.create(message=message, image=image)


class SupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="List my support tickets",
        description=(
            "Retrieve all support tickets belonging to the authenticated user, "
            "including their full message threads and any image attachments. "
            "Attachment image URLs are absolute and point to the uploaded file."
        ),
        operation_id="support_tickets_list",
        responses={200: SupportTicketListResponse},
        tags=["Support"],
        examples=[
            OpenApiExample(
                "Ticket list",
                summary="List of the user's tickets",
                value={
                    "count": 1,
                    "tickets": [
                        {
                            "id": 1,
                            "subject": "Cannot withdraw funds",
                            "description": "Withdrawal fails with error 500.",
                            "status": "open",
                            "priority": "high",
                            "created_at": "2026-08-25T10:00:00Z",
                            "updated_at": "2026-08-25T10:05:00Z",
                            "messages": [
                                {
                                    "id": 1,
                                    "sender_name": "John Doe",
                                    "message": "Withdrawal fails with error 500.",
                                    "is_admin": False,
                                    "created_at": "2026-08-25T10:00:00Z",
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
    def get(self, request):
        tickets = SupportTicket.objects.filter(user=request.user).order_by(
            "-created_at"
        )
        serializer = SupportTicketSerializer(
            tickets, many=True, context={"request": request}
        )
        return Response(
            {"count": tickets.count(), "tickets": serializer.data},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Create a support ticket",
        description=(
            "Create a new support ticket for the authenticated user. The provided "
            "`description` becomes the ticket's first message. Optional `images` is an "
            "array of image files (multipart/form-data) attached to that first message. "
            "Only the ticket owner can later view or reply to the ticket."
        ),
        operation_id="support_ticket_create",
        request=CreateTicketSerializer,
        responses={201: CreateTicketResponse, 400: OpenApiTypes.OBJECT},
        tags=["Support"],
        examples=[
            OpenApiExample(
                "Create ticket",
                summary="Create a ticket with priority and an image",
                description=(
                    "Send as multipart/form-data. `images` is one or more image "
                    "files uploaded as form fields (not JSON strings)."
                ),
                value={
                    "subject": "Cannot withdraw funds",
                    "description": "Withdrawal fails with error 500.",
                    "priority": "high",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Created",
                summary="201 response",
                value={
                    "success": True,
                    "message": "Support ticket created successfully",
                    "ticket": {
                        "id": 1,
                        "subject": "Cannot withdraw funds",
                        "description": "Withdrawal fails with error 500.",
                        "status": "open",
                        "priority": "high",
                        "created_at": "2026-08-25T10:00:00Z",
                        "updated_at": "2026-08-25T10:00:00Z",
                        "messages": [
                            {
                                "id": 1,
                                "sender_name": "John Doe",
                                "message": "Withdrawal fails with error 500.",
                                "is_admin": False,
                                "created_at": "2026-08-25T10:00:00Z",
                                "attachments": [],
                            }
                        ],
                    },
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = CreateTicketSerializer(data=request.data)
        if serializer.is_valid():
            ticket = serializer.save(user=request.user)
            # Create initial message
            message = SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=serializer.validated_data["description"],
            )
            images = request.FILES.getlist("images")
            if images:
                create_attachments(message, images)
            return Response(
                {
                    "success": True,
                    "message": "Support ticket created successfully",
                    "ticket": SupportTicketSerializer(
                        ticket, context={"request": request}
                    ).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class SupportTicketDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Get support ticket detail",
        description=(
            "Retrieve a single support ticket with its full message thread and "
            "image attachments for the authenticated user. Returns 404 if the "
            "ticket does not exist or is not owned by the user."
        ),
        operation_id="support_ticket_retrieve",
        responses={200: SupportTicketSerializer, 404: OpenApiTypes.OBJECT},
        tags=["Support"],
        examples=[
            OpenApiExample(
                "Not found",
                summary="404 when ticket is missing or not owned",
                value={"error": "Ticket not found"},
                response_only=True,
                status_codes=["404"],
            )
        ],
    )
    def get(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            serializer = SupportTicketSerializer(ticket, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Add a message to a support ticket",
        description=(
            "Append a message to an existing support ticket owned by the "
            "authenticated user. Optional `images` is an array of image files "
            "(multipart/form-data) attached to the new message. Returns 404 if "
            "the ticket does not exist or is not owned by the user."
        ),
        operation_id="support_ticket_add_message",
        request=AddMessageSerializer,
        responses={
            201: AddMessageResponse,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=["Support"],
        examples=[
            OpenApiExample(
                "Add message",
                summary="Reply with an image attachment",
                description=(
                    "Send as multipart/form-data. `images` is one or more image "
                    "files uploaded as form fields."
                ),
                value={"message": "Here is the screenshot of the error.", "images": []},
                request_only=True,
            ),
            OpenApiExample(
                "Added",
                summary="201 response",
                value={
                    "success": True,
                    "message": {
                        "id": 2,
                        "sender_name": "John Doe",
                        "message": "Here is the screenshot of the error.",
                        "is_admin": False,
                        "created_at": "2026-08-25T10:10:00Z",
                        "attachments": [
                            {
                                "id": 1,
                                "image": "https://api.bluesea.app/media/support_attachments/2026/08/25/err.png",
                                "uploaded_at": "2026-08-25T10:10:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
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
                images = request.FILES.getlist("images")
                if images:
                    create_attachments(message, images)
                return Response(
                    {
                        "success": True,
                        "message": SupportMessageSerializer(
                            message, context={"request": request}
                        ).data,
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
