from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from unittest import mock
from accounts.models import Profile
from user_preference.models import UpdateUserModel


@override_settings(
    SECURE_SSL_REDIRECT=False,
)
@mock.patch("silk.middleware._should_intercept", return_value=False)
class CurrentUserQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="pref@example.com",
            phone="08060000001",
            surname="Pref",
            other_names="User",
            role="user",
        )
        UpdateUserModel.objects.get_or_create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_current_user_query_count_is_bounded(self, mock_should_intercept):
        # preference lookup only (request.user already loaded); no N+1
        with self.assertNumQueries(1):
            resp = self.client.get(reverse("user_preference:user"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("preference", resp.data)
