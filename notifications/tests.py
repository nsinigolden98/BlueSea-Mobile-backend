from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from unittest import mock
from accounts.models import Profile
from notifications.models import Notification


@override_settings(
    SECURE_SSL_REDIRECT=False,
)
@mock.patch("silk.middleware._should_intercept", return_value=False)
class NotificationQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="notif@example.com",
            phone="08020000001",
            surname="Notif",
            other_names="Test",
            role="user",
        )
        for i in range(25):
            Notification.objects.create(
                user=self.user,
                title=f"Title {i}",
                message=f"Message {i}",
                notification_type="info",
                is_read=(i % 2 == 0),
            )

    def test_notification_list_query_count_is_bounded(self, mock_should_intercept):
        self.client.force_authenticate(user=self.user)
        # unread count + DRF pagination count + page fetch (bounded, no N+1)
        with self.assertNumQueries(3):
            resp = self.client.get(reverse("notification-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unread_count"], 12)
        self.assertEqual(len(resp.data["results"]), 20)
