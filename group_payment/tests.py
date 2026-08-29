import uuid
from decimal import Decimal
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Profile
from wallet.models import Wallet
from group_payment.models import Group, GroupMember


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MIDDLEWARE=[m for m in settings.MIDDLEWARE if "silk" not in m],
    SILKY_INTERCEPT_REQUEST=False,
    SILKY_META=False,
)
class GroupListQueryCountTestCase(APITestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="grouplist@example.com",
            phone="08010000001",
            surname="Group",
            other_names="List",
            role="user",
        )
        Wallet.objects.create(user=self.user, balance=Decimal("1000.00"))

        # Several groups with differing member/payment mixes -> exposes the
        # original 3N .count() queries inside ListMyGroupsView.
        for i in range(3):
            group = Group.objects.create(
                name=f"Group {i}",
                service_type="airtime",
                sub_number="123",
                target_amount=1000,
                current_amount=0,
                created_by=self.user,
                status="pending",
            )
            GroupMember.objects.create(
                group=group,
                user=self.user,
                role="owner",
                payment_status="paid",
            )
            # Add one pending member to each group so paid/pending counts differ
            member_user = Profile.objects.create_user(
                email=f"gmember{i}@example.com",
                phone=f"0801000000{i}",
                surname="M",
                other_names=str(i),
                role="user",
            )
            GroupMember.objects.create(
                group=group,
                user=member_user,
                role="member",
                payment_status="pending",
            )

    def test_my_groups_query_count_is_bounded(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(2):
            resp = self.client.get(reverse("my-groups"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 3)
        # First group: 1 paid (owner) + 1 pending member
        first = resp.data["groups"][0]
        self.assertEqual(first["member_count"], 2)
        self.assertEqual(first["paid_members"], 1)
        self.assertEqual(first["pending_members"], 1)
