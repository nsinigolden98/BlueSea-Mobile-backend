from decimal import Decimal
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Profile
from wallet.models import Wallet
from loyalty_market.models import Reward, RedemptionTransaction


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MIDDLEWARE=[m for m in settings.MIDDLEWARE if "silk" not in m],
    SILKY_INTERCEPT_REQUEST=False,
    SILKY_META=False,
)
class LoyaltyRedemptionsQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="loyalty@example.com",
            phone="08010000001",
            surname="Loyal",
            other_names="Ty",
            role="user",
        )
        Wallet.objects.create(user=self.user, balance=Decimal("1000.00"))

        owner = Profile.objects.create_user(
            email="rewardowner@example.com",
            phone="08010000002",
            surname="Owner",
            other_names="R",
            role="user",
        )
        reward = Reward.objects.create(
            user=owner,
            title="Test Reward",
            description="desc",
            points_cost=10,
            category="test",
            inventory=5,
        )
        # Many redemptions -> exposes N+1 on r.reward_id.title
        for _ in range(5):
            RedemptionTransaction.objects.create(
                user_id=self.user,
                reward_id=reward,
                points_deducted=10,
                status="completed",
            )

    def test_user_redemptions_query_count_is_bounded(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(1):
            resp = self.client.get(reverse("user-redemptions"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 5)
        self.assertEqual(len(resp.data["redemptions"]), 5)
