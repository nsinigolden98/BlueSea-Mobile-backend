from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from accounts.crypto import encrypt_pin
from market_place.models import EventInfo, IssuedTicket, TicketType, TicketVendor
from wallet.models import Wallet

from .models import AffiliateLink, AffiliateProfile, AffiliateSale

enc = encrypt_pin

BLANK_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x00\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)


@override_settings(SECURE_SSL_REDIRECT=False)
class AffiliateFlowTestCase(APITestCase):
    def setUp(self):
        # Vendor + event + ticket type
        self.vendor_user = Profile.objects.create_user(
            email="vendor@example.com",
            phone="08010000001",
            surname="Vendor",
            other_names="One",
            role="user",
        )
        self.vendor = TicketVendor.objects.create(
            user=self.vendor_user,
            business_type="individual",
            brand_name="Smoke Vendor",
            legal_full_name="Vendor Legal",
            phone_number=self.vendor_user.phone,
            email=self.vendor_user.email,
            is_verified=True,
        )
        self.event = EventInfo.objects.create(
            vendor=self.vendor,
            event_title="Smoke Event",
            hosted_by="Smoke Vendor",
            category="Music",
            event_banner=SimpleUploadedFile(
                "banner.gif", BLANK_GIF, content_type="image/gif"
            ),
            event_date=timezone.now() + timedelta(days=10),
            event_location="Lagos",
            is_free=False,
            is_approved=True,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Regular",
            price=Decimal("10000.00"),
            quantity_available=100,
            initial_quantity=100,
        )

        self.event2 = EventInfo.objects.create(
            vendor=self.vendor,
            event_title="Smoke Event 2",
            hosted_by="Smoke Vendor",
            category="Music",
            event_banner=SimpleUploadedFile(
                "banner2.gif", BLANK_GIF, content_type="image/gif"
            ),
            event_date=timezone.now() + timedelta(days=20),
            event_location="Lagos",
            is_free=False,
            is_approved=True,
        )
        self.ticket_type2 = TicketType.objects.create(
            event=self.event2,
            name="Regular",
            price=Decimal("5000.00"),
            quantity_available=100,
            initial_quantity=100,
        )

        # Affiliate + buyer users (with wallets)
        self.affiliate_user = self._make_user(
            "affiliate@example.com", "08010000002", "Affiliate", "User"
        )
        self.buyer_user = self._make_user(
            "buyer@example.com", "08010000003", "Buyer", "User"
        )
        self.other_user = self._make_user(
            "other@example.com", "08010000004", "Other", "User"
        )

        self.buyer_user.set_transaction_pin(enc("1234"))

    def _make_user(self, email, phone, surname, other_names):
        user = Profile.objects.create_user(
            email=email,
            phone=phone,
            surname=surname,
            other_names=other_names,
            role="user",
        )
        Wallet.objects.create(user=user, balance=Decimal("100000.00"))
        return user

    def _apply(self, user, name="smokeaff", agreement=True):
        self.client.force_authenticate(user=user)
        return self.client.post(
            reverse("affiliate-apply"),
            {"affiliate_name": name, "agreement": agreement},
            format="json",
        )

    def _approve(self, profile):
        profile.approve()

    def test_apply_and_duplicate_name(self):
        resp = self._apply(self.affiliate_user)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "pending")
        self.assertTrue(resp.data["agreement_accepted"])

        dup = self._apply(self.other_user, name="smokeaff")
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already taken", str(dup.data))

        no_agreement = self._apply(self.other_user, name="othername", agreement=False)
        self.assertEqual(no_agreement.status_code, status.HTTP_400_BAD_REQUEST)

    def test_full_flow_commission_payout_and_revoke(self):
        # Apply + approve
        self._apply(self.affiliate_user)
        profile = AffiliateProfile.objects.get(affiliate_name="smokeaff")
        self._approve(profile)

        # Generate link (must be approved)
        self.client.force_authenticate(user=self.affiliate_user)
        link_resp = self.client.post(
            reverse("affiliate-links"), {"event_id": str(self.event.id)}, format="json"
        )
        self.assertEqual(link_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(link_resp.data["commission_rate"], "2.00")
        self.assertIn("affiliate=smokeaff", link_resp.data["link"])
        link = AffiliateLink.objects.get(affiliate=profile, event=self.event)

        # Attribution (pending)
        self.client.force_authenticate(user=self.buyer_user)
        attr_resp = self.client.post(
            reverse("affiliate-attribution"),
            {"event_id": str(self.event.id), "affiliate_username": "smokeaff"},
            format="json",
        )
        self.assertEqual(attr_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(attr_resp.data["status"], "pending")

        # Purchase with affiliate_username -> success
        self.client.force_authenticate(user=self.buyer_user)
        purch = self.client.post(
            reverse("purchase-ticket", kwargs={"event_id": self.event.id}),
            {
                "ticket_type": "Regular",
                "quantity": 2,
                "transaction_pin": enc("1234"),
                "affiliate_username": "smokeaff",
            },
            format="json",
        )
        self.assertEqual(purch.status_code, status.HTTP_201_CREATED)

        sale = AffiliateSale.objects.get(affiliate=profile, buyer=self.buyer_user)
        self.assertEqual(sale.status, "success")
        self.assertEqual(sale.ticket_count, 2)
        self.assertEqual(sale.gross_amount, Decimal("20000.00"))
        self.assertEqual(sale.commission_amount, Decimal("400.00"))  # 2%
        self.assertEqual(sale.commission_rate, Decimal("2.00"))
        self.assertIsNotNone(sale.issued_ticket)

        # Sweep payable once event date passes
        self.event.event_date = timezone.now() - timedelta(days=1)
        self.event.save(update_fields=["event_date"])
        self.client.force_authenticate(user=self.affiliate_user)
        dash = self.client.get(reverse("affiliate-dashboard"))
        self.assertEqual(dash.status_code, status.HTTP_200_OK)
        sale.refresh_from_db()
        self.assertEqual(sale.status, "payable")
        self.assertEqual(dash.data["payable_amount"], Decimal("400.00"))

        # Payout -> wallet credited
        payout = self.client.post(reverse("affiliate-payout"))
        self.assertEqual(payout.status_code, status.HTTP_200_OK)
        sale.refresh_from_db()
        self.assertEqual(sale.status, "paid")
        self.affiliate_user.refresh_from_db()
        self.assertEqual(
            self.affiliate_user.wallet.balance, Decimal("100000.00") + Decimal("400.00")
        )

    def test_revoke_on_cancel(self):
        self._apply(self.affiliate_user)
        profile = AffiliateProfile.objects.get(affiliate_name="smokeaff")
        self._approve(profile)

        # Generate link for the second (future) event
        self.client.force_authenticate(user=self.affiliate_user)
        link_resp = self.client.post(
            reverse("affiliate-links"), {"event_id": str(self.event2.id)}, format="json"
        )
        self.assertEqual(link_resp.status_code, status.HTTP_200_OK)

        # Buy through affiliate
        self.client.force_authenticate(user=self.buyer_user)
        purch = self.client.post(
            reverse("purchase-ticket", kwargs={"event_id": self.event2.id}),
            {
                "ticket_type": "Regular",
                "quantity": 1,
                "transaction_pin": enc("1234"),
                "affiliate_username": "smokeaff",
            },
            format="json",
        )
        self.assertEqual(purch.status_code, status.HTTP_201_CREATED)

        sale = AffiliateSale.objects.get(affiliate=profile, buyer=self.buyer_user)
        self.assertEqual(sale.status, "success")

        # Cancel the attributed ticket -> sale revoked
        ticket = IssuedTicket.objects.filter(
            event=self.event2, purchased_by=self.buyer_user
        ).first()
        self.assertIsNotNone(ticket)
        cancel = self.client.post(
            reverse("cancel-ticket", kwargs={"ticket_id": ticket.id}),
            {"reason": "changed my mind", "transaction_pin": enc("1234")},
            format="json",
        )
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        sale.refresh_from_db()
        self.assertEqual(sale.status, "revoked")
        self.assertIsNotNone(sale.revoked_at)

    def test_link_requires_approval(self):
        self._apply(self.affiliate_user)
        self.client.force_authenticate(user=self.affiliate_user)
        resp = self.client.post(
            reverse("affiliate-links"), {"event_id": str(self.event.id)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_first_attribution_wins(self):
        self._apply(self.affiliate_user)
        profile = AffiliateProfile.objects.get(affiliate_name="smokeaff")
        self._approve(profile)
        self.client.force_authenticate(user=self.affiliate_user)
        self.client.post(
            reverse("affiliate-links"), {"event_id": str(self.event.id)}, format="json"
        )

        self.client.force_authenticate(user=self.buyer_user)
        resp = self.client.post(
            reverse("affiliate-attribution"),
            {"event_id": str(self.event.id), "affiliate_username": "smokeaff"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(AffiliateSale.objects.filter(buyer=self.buyer_user).count(), 1)

        # Buying through another affiliate should not create a second pending sale
        self._apply(self.other_user, name="secondaff")
        profile2 = AffiliateProfile.objects.get(affiliate_name="secondaff")
        self._approve(profile2)
        self.client.force_authenticate(user=self.other_user)
        self.client.post(
            reverse("affiliate-links"), {"event_id": str(self.event.id)}, format="json"
        )
        self.client.force_authenticate(user=self.buyer_user)
        resp2 = self.client.post(
            reverse("affiliate-attribution"),
            {"event_id": str(self.event.id), "affiliate_username": "secondaff"},
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(AffiliateSale.objects.filter(buyer=self.buyer_user).count(), 1)
