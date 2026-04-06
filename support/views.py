from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import SupportTicket, SupportMessage
from .serializers import (
    SupportTicketSerializer,
    CreateTicketSerializer,
    AddMessageSerializer,
    SupportMessageSerializer,
)


class SupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = SupportTicket.objects.filter(user=request.user).order_by(
            "-created_at"
        )
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(
            {"count": tickets.count(), "tickets": serializer.data},
            status=status.HTTP_200_OK,
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

    def get(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            serializer = SupportTicketSerializer(ticket)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
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
