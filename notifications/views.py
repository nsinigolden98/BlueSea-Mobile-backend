from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Notification
from .serializers import NotificationSerializer
from django.utils import timezone

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)
        
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            notifications = notifications.filter(is_read=is_read_bool)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            'count': notifications.count(),
            'unread_count': notifications.filter(is_read=False).count(),
            'notifications': serializer.data
        }, status=status.HTTP_200_OK)


class MarkNotificationAsReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.mark_as_read()
            
            return Response({
                'message': 'Notification marked as read',
                'notification': NotificationSerializer(notification).data
            }, status=status.HTTP_200_OK)
            
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class MarkAllNotificationsAsReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({
            'message': f'{updated_count} notifications marked as read'
        }, status=status.HTTP_200_OK)



class DeleteNotificationView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.delete()
            
            return Response({
                'message': 'Notification deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )