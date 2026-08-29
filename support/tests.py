import io
import os
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from PIL import Image

from accounts.models import Profile
from support.models import SupportTicket, SupportMessage, SupportAttachment


def make_image(name="test.png", size=(10, 10), color=(255, 0, 0)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    buffer.seek(0)
    buffer.name = name
    return buffer


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MEDIA_ROOT=os.path.join(settings.BASE_DIR, "media", "test_tmp"),
)
class SupportImageTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="supportuser@example.com",
            phone="08011112222",
            surname="Support",
            other_names="User",
            role="user",
        )
        self.client.force_authenticate(user=self.user)
        self.list_url = reverse("support-tickets")

    def _create_ticket_with_images(self, count=2):
        data = {
            "subject": "Broken feature",
            "description": "It does not work",
            "priority": "high",
            "images": [make_image(name=f"img{i}.png") for i in range(count)],
        }
        return self.client.post(self.list_url, data, format="multipart")

    def test_create_ticket_with_multiple_images(self):
        response = self._create_ticket_with_images(2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket = SupportTicket.objects.first()
        self.assertEqual(ticket.messages.count(), 1)
        message = ticket.messages.first()
        self.assertEqual(message.attachments.count(), 2)
        self.assertIn(
            "http", response.data["ticket"]["messages"][0]["attachments"][0]["image"]
        )

    def test_create_ticket_without_images(self):
        response = self.client.post(
            self.list_url,
            {
                "subject": "No image",
                "description": "plain",
                "priority": "low",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SupportMessage.objects.first().attachments.count(), 0)

    def test_add_message_with_images(self):
        create = self._create_ticket_with_images(1)
        ticket_id = create.data["ticket"]["id"]
        url = reverse("support-ticket-detail", kwargs={"ticket_id": ticket_id})
        data = {"message": "Here is a screenshot", "images": make_image(name="m.png")}
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = SupportMessage.objects.get(
            ticket_id=ticket_id, message="Here is a screenshot"
        )
        self.assertEqual(message.attachments.count(), 1)

    def test_list_ticket_includes_attachments(self):
        self._create_ticket_with_images(1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attachments = response.data["tickets"][0]["messages"][0]["attachments"]
        self.assertEqual(len(attachments), 1)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MEDIA_ROOT=os.path.join(settings.BASE_DIR, "media", "test_tmp"),
)
@mock.patch("silk.middleware._should_intercept", return_value=False)
class SupportQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="supportq@example.com",
            phone="08044445555",
            surname="Support",
            other_names="Query",
            role="user",
        )
        self.client.force_authenticate(user=self.user)
        self.list_url = reverse("support-tickets")
        for t in range(3):
            ticket = SupportTicket.objects.create(
                user=self.user,
                subject=f"Subject {t}",
                description=f"Desc {t}",
                priority="high",
            )
            for m in range(2):
                SupportMessage.objects.create(
                    ticket=ticket,
                    sender=self.user,
                    message=f"Message {t}-{m}",
                )

    def test_support_ticket_list_query_count_is_bounded(self, mock_should_intercept):
        # tickets + messages prefetch + sender prefetch + attachments prefetch
        with self.assertNumQueries(4):
            response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["tickets"]), 3)
        self.assertEqual(len(response.data["tickets"][0]["messages"]), 2)

    def test_support_ticket_detail_query_count_is_bounded(self, mock_should_intercept):
        ticket = SupportTicket.objects.first()
        url = reverse("support-ticket-detail", kwargs={"ticket_id": ticket.id})
        # ticket + messages prefetch + sender prefetch + attachments prefetch
        with self.assertNumQueries(4):
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["messages"]), 2)
