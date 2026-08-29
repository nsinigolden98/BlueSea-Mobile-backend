from decimal import Decimal
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Profile
from wallet.models import Wallet
from bonus.models import Referral


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MIDDLEWARE=[m for m in settings.MIDDLEWARE if "silk" not in m],
    SILKY_INTERCEPT_REQUEST=False,
    SILKY_META=False,
)
class BonusReferralQueryCountTestCase(APITestCase):
    def setUp(self):
        self.referrer = Profile.objects.create_user(
            email="referrer@example.com",
            phone="08010000001",
            surname="Ref",
            other_names="Errer",
            role="user",
        )
        Wallet.objects.create(user=self.referrer, balance=Decimal("1000.00"))

        # Many referred users, each with a Referral row -> exposes N+1 on
        # referrer.email / referred_user.email in ReferralSerializer.
        for i in range(5):
            referred = Profile.objects.create_user(
                email=f"referred{i}@example.com",
                phone=f"0801000000{i}",
                surname="Refd",
                other_names=str(i),
                role="user",
            )
            Referral.objects.create(
                referrer=self.referrer,
                referred_user=referred,
                referral_code=self.referrer.referral_code,
                status="completed",
            )

    def test_referral_list_query_count_is_bounded(self):
        self.client.force_authenticate(user=self.referrer)
        with self.assertNumQueries(2):
            resp = self.client.get(reverse("bonus:referral"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["referral_count"], 5)
        self.assertEqual(resp.data["completed_count"], 5)
        self.assertEqual(len(resp.data["data"]), 5)
