from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from unittest import mock
from accounts.models import Profile
from wallet.models import Wallet


@override_settings(
    SECURE_SSL_REDIRECT=False,
)
@mock.patch("silk.middleware._should_intercept", return_value=False)
class WalletBalanceQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="wallet@example.com",
            phone="08070000001",
            surname="Wallet",
            other_names="User",
            role="user",
        )
        Wallet.objects.create(user=self.user, balance=5000)
        self.client.force_authenticate(user=self.user)

    def test_wallet_balance_query_count_is_bounded(self, mock_should_intercept):
        # single wallet lookup; no N+1
        with self.assertNumQueries(1):
            resp = self.client.get(reverse("wallet-balance"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("balance", resp.data)
