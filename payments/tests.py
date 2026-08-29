from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from unittest import mock
from accounts.models import Profile
from group_payment.models import Group, GroupMember
from payments.models import GroupPayment, GroupPaymentContribution


@override_settings(
    SECURE_SSL_REDIRECT=False,
)
@mock.patch("silk.middleware._should_intercept", return_value=False)
class PaymentHistoryQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="payhist@example.com",
            phone="08030000001",
            surname="Pay",
            other_names="Hist",
            role="user",
        )
        self.group = Group.objects.create(
            name="Pay Group",
            created_by=self.user,
            service_type="airtime",
        )
        GroupMember.objects.create(group=self.group, user=self.user, role="owner")
        payment = GroupPayment.objects.create(
            group=self.group,
            initiated_by=self.user,
            payment_type="airtime",
            total_amount=100,
            service_details={},
            status="completed",
        )
        member = GroupMember.objects.get(group=self.group, user=self.user)
        for i in range(3):
            GroupPaymentContribution.objects.create(
                group_payment=payment,
                member=member,
                amount=30,
                status="completed",
            )

    def test_group_payment_history_query_count_is_bounded(self, mock_should_intercept):
        self.client.force_authenticate(user=self.user)
        # user_groups lookup + payments (select_related) + contributions prefetch
        # + member__user prefetch
        with self.assertNumQueries(4):
            resp = self.client.get(reverse("group-payment-history"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(len(resp.data[0]["contributions"]), 3)
