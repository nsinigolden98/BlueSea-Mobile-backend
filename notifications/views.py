from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Notification
from .serializers import NotificationSerializer, NotificationListResponse
from .pagination import NotificationPagination
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    paginator = NotificationPagination()

    @extend_schema(
        summary="List notifications",
        description="List the authenticated user's notifications, newest first.",
        parameters=[
            OpenApiParameter(
                "is_read",
                OpenApiTypes.BOOL,
                required=False,
                description="Filter by read status (true/false)",
            )
        ],
        responses={200: NotificationListResponse},
        tags=["Notifications"],
    )
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by(
            "-created_at"
        )

        is_read = request.query_params.get("is_read")
        if is_read is not None:
            is_read_bool = is_read.lower() == "true"
            notifications = notifications.filter(is_read=is_read_bool)

        # Get unread count
        unread_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()

        page = self.paginator.paginate_queryset(notifications, request, view=self)
        serializer = NotificationSerializer(page, many=True)

        response = self.paginator.get_paginated_response(serializer.data)
        response.data["unread_count"] = unread_count

        return response


class MarkNotificationAsReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Mark a notification as read",
        parameters=[
            OpenApiParameter(
                "notification_id", OpenApiTypes.INT, OpenApiParameter.PATH
            )
        ],
        request=None,
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=["Notifications"],
    )
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id, user=request.user
            )
            notification.mark_as_read()

            return Response(
                {
                    "message": "Notification marked as read",
                    "notification": NotificationSerializer(notification).data,
                },
                status=status.HTTP_200_OK,
            )

        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
            )


class MarkAllNotificationsAsReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Mark all notifications as read",
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        tags=["Notifications"],
    )
    def post(self, request):
        updated_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        return Response(
            {"message": f"{updated_count} notifications marked as read"},
            status=status.HTTP_200_OK,
        )


class DeleteNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete a notification",
        parameters=[
            OpenApiParameter(
                "notification_id", OpenApiTypes.INT, OpenApiParameter.PATH
            )
        ],
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=["Notifications"],
    )
    def delete(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id, user=request.user
            )
            notification.delete()

            return Response(
                {"message": "Notification deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
            )
