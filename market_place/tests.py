from django.urls import reverse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import Profile
from market_place.models import TicketVendor, EventInfo, EventScanner
from market_place.serializers import CreateEventSerializer


def _make_image(name="banner.png"):
    img = Image.new("RGB", (10, 10), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(SECURE_SSL_REDIRECT=False)
class AddEventScannerViewTestCase(APITestCase):
    def setUp(self):
        # Create vendors
        self.vendor_user = Profile.objects.create_user(
            email="vendor@example.com",
            phone="08012345678",
            surname="Vendor",
            other_names="User",
            role="user",
        )
        self.vendor_user.email_verified = True
        self.vendor_user.save()

        self.vendor = TicketVendor.objects.create(
            user=self.vendor_user,
            business_type="individual",
            brand_name="Vendor Brand",
            legal_full_name="Vendor Legal Name",
            phone_number=self.vendor_user.phone,
            email=self.vendor_user.email,
            is_verified=True,
            verification_status="approved",
        )
        # Verify vendor user role is synced (usually done in admin, but set here)
        self.vendor_user.role = "vendor"
        self.vendor_user.save()

        self.other_vendor_user = Profile.objects.create_user(
            email="other_vendor@example.com",
            phone="08012345679",
            surname="Other",
            other_names="Vendor",
            role="vendor",
        )
        self.other_vendor = TicketVendor.objects.create(
            user=self.other_vendor_user,
            business_type="individual",
            brand_name="Other Vendor Brand",
            legal_full_name="Other Vendor Legal",
            phone_number=self.other_vendor_user.phone,
            email=self.other_vendor_user.email,
            is_verified=True,
            verification_status="approved",
        )

        # Create scanner users
        self.scanner_user = Profile.objects.create_user(
            email="scanner@example.com",
            phone="08087654321",
            surname="Scanner",
            other_names="User",
            role="user",
        )

        # Create events
        self.event = EventInfo.objects.create(
            vendor=self.vendor,
            event_title="Vendor Event",
            hosted_by="Vendor Brand",
            category="Music",
            event_date=timezone.now() + timedelta(days=5),
            event_location="Lagos",
            is_approved=True,
        )

        self.other_event = EventInfo.objects.create(
            vendor=self.other_vendor,
            event_title="Other Vendor Event",
            hosted_by="Other Vendor Brand",
            category="Art",
            event_date=timezone.now() + timedelta(days=10),
            event_location="Lagos",
            is_approved=True,
        )

        self.url = reverse("add-event-scanner", kwargs={"event_id": self.event.id})

    def test_successful_scanner_assignment(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            self.url, data={"user_email": "scanner@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["state"])
        self.assertTrue(
            EventScanner.objects.filter(
                user=self.scanner_user, event=self.event
            ).exists()
        )

        # Verify scanner user role updated to "scanner"
        self.scanner_user.refresh_from_db()
        self.assertEqual(self.scanner_user.role, "scanner")

    def test_case_insensitive_and_stripped_scanner_assignment(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            self.url, data={"user_email": "  ScAnNeR@eXaMpLe.CoM  "}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["state"])
        self.assertTrue(
            EventScanner.objects.filter(
                user=self.scanner_user, event=self.event
            ).exists()
        )

        self.scanner_user.refresh_from_db()
        self.assertEqual(self.scanner_user.role, "scanner")

    def test_already_assigned_scanner_returns_400(self):
        # Pre-create scanner assignment
        EventScanner.objects.create(user=self.scanner_user, event=self.event)

        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            self.url, data={"user_email": "scanner@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["state"])
        self.assertIn("already assigned", response.data["error"])

    def test_non_existent_user_returns_404(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            self.url, data={"user_email": "nonexistent@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data["state"])
        self.assertIn("not found", response.data["error"])

    def test_unauthorized_non_owner_vendor_returns_403(self):
        # Attempting to add scanner to other_vendor's event
        unauthorized_url = reverse(
            "add-event-scanner", kwargs={"event_id": self.other_event.id}
        )

        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(
            unauthorized_url, data={"user_email": "scanner@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["state"])
        self.assertIn("own events", response.data["error"])

    def test_missing_parameters_returns_400(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["state"])
        self.assertIn("required", response.data["error"])


@override_settings(SECURE_SSL_REDIRECT=False)
class CreateEventModeTestCase(APITestCase):
    def setUp(self):
        self.vendor_user = Profile.objects.create_user(
            email="mode_vendor@example.com",
            phone="08012345678",
            surname="Mode",
            other_names="Vendor",
            role="vendor",
        )
        self.vendor = TicketVendor.objects.create(
            user=self.vendor_user,
            business_type="individual",
            brand_name="Mode Brand",
            legal_full_name="Mode Legal",
            phone_number=self.vendor_user.phone,
            email=self.vendor_user.email,
            is_verified=True,
            verification_status="approved",
        )

    def _valid_data(self, **overrides):
        data = {
            "vendor": self.vendor.id,
            "event_title": "Mode Test Event",
            "hosted_by": "Mode Brand",
            "category": "Music",
            "event_date": (timezone.now() + timedelta(days=5)).isoformat(),
            "event_mode": "offline",
            "event_location": "Lagos",
            "meeting_link": "",
            "is_free": True,
            "quantity": 100,
            "event_banner": _make_image(),
        }
        data.update(overrides)
        return data

    def test_offline_valid(self):
        ser = CreateEventSerializer(data=self._valid_data())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_offline_missing_location_invalid(self):
        ser = CreateEventSerializer(data=self._valid_data(event_location=""))
        self.assertFalse(ser.is_valid())
        self.assertIn("event_location", ser.errors)

    def test_online_valid(self):
        ser = CreateEventSerializer(
            data=self._valid_data(
                event_mode="online",
                event_location="",
                meeting_link="https://meet.example.com/room",
            )
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_online_missing_link_invalid(self):
        ser = CreateEventSerializer(
            data=self._valid_data(
                event_mode="online", event_location="", meeting_link=""
            )
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("meeting_link", ser.errors)

    def test_hybrid_valid(self):
        ser = CreateEventSerializer(
            data=self._valid_data(
                event_mode="hybrid", meeting_link="https://meet.example.com/room"
            )
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_hybrid_missing_link_invalid(self):
        ser = CreateEventSerializer(
            data=self._valid_data(event_mode="hybrid", meeting_link="")
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("meeting_link", ser.errors)

    def test_unknown_mode_invalid(self):
        ser = CreateEventSerializer(data=self._valid_data(event_mode="spaceship"))
        self.assertFalse(ser.is_valid())
        self.assertIn("event_mode", ser.errors)
