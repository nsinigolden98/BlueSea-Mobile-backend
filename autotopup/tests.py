from decimal import Decimal
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase

from accounts.models import Profile
from wallet.models import Wallet
from .models import AutoTopUp, AutoTopUpHistory


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MIDDLEWARE=[m for m in settings.MIDDLEWARE if "silk" not in m],
    SILKY_INTERCEPT_REQUEST=False,
    SILKY_META=False,
)
class AutoTopUpQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="autotopup@example.com",
            phone="08010000001",
            surname="Auto",
            other_names="TopUp",
            role="user",
        )
        Wallet.objects.create(user=self.user, balance=Decimal("100000.00"))

        now = timezone.now()
        self.auto_topup = AutoTopUp.objects.create(
            user=self.user,
            service_type="airtime",
            amount=Decimal("100.00"),
            phone_number="08012345678",
            network="mtn",
            start_date=now,
            next_run=now + timedelta(days=1),
        )
        # Many history rows to expose any N+1 on the history/auto_topup FK
        for i in range(5):
            AutoTopUpHistory.objects.create(
                auto_topup=self.auto_topup,
                amount=Decimal("100.00"),
                status="success",
                vtu_reference=f"VTU-{i}",
            )

    def test_history_query_count_is_bounded(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(2):
            resp = self.client.get(
                reverse("auto-topup-history", kwargs={"pk": self.auto_topup.id})
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 5)

    def test_detail_query_count_is_bounded(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(2):
            resp = self.client.get(
                reverse("auto-topup-detail", kwargs={"pk": self.auto_topup.id})
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["history"]), 5)
