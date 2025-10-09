from django.urls import path
from .views import (
    NotificationListView,
    MarkNotificationAsReadView,
    MarkAllNotificationsAsReadView,
    DeleteNotificationView
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:notification_id>/read/', MarkNotificationAsReadView.as_view(), name='mark-notification-read'),
    path('mark-all-read/', MarkAllNotificationsAsReadView.as_view(), name='mark-all-notifications-read'),
    path('<int:notification_id>/delete/', DeleteNotificationView.as_view(), name='delete-notification'),
]