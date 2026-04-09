import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Group, GroupMember
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes


class CreateGroupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create a new group",
        description="Create a payment group and automatically become the owner",
        request=OpenApiTypes.OBJECT,
        responses={201: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Create Group",
                value={
                    "name": "Family Group",
                    "description": "Group for family bill payments",
                },
                request_only=True,
            )
        ],
        tags=["Group Payments"],
    )
    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response(
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            name = request.data.get("name")
            description = request.data.get("description", "")
            service_type = request.data.get("service_type")
            sub_number = request.data.get("sub_number")
            target_amount = request.data.get("target_amount")
            invite_members = request.data.get("invite_members")
            plan = request.data.get("plan")
            plan_type = request.data.get("plan_type", "")

            if not name:
                return Response(
                    {"error": "Group name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not service_type:
                return Response(
                    {"error": "Service type is required (airtime, data, or lightbill)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Require sub_number
            if not sub_number:
                return Response(
                    {"error": "Phone/account number is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Require plan for data service type
            if service_type == "data" and not plan:
                return Response(
                    {"error": "Plan is required for data service type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate invite members - ALL emails must exist in database
            from accounts.models import Profile

            invalid_users = set()
            valid_emails = set()

            if invite_members:
                email_list = [
                    email.strip()
                    for email in invite_members.split(",")
                    if email.strip()
                ]

                for email in email_list:
                    if Profile.objects.filter(email__iexact=email).exists():
                        valid_emails.add(email)
                    else:
                        invalid_users.add(email)

                # Block group creation if ANY invalid users found
                if invalid_users:
                    return Response(
                        {
                            "error": "Invalid invite: some users do not exist in the system. Group not created.",
                            "invalid_users": invalid_users,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                elif request.user.email in email_list:
                    return Response(
                        {
                            "error": "You can not invite yourself. Group not created.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Create group
            group = Group.objects.create(
                name=name,
                description=description,
                service_type=service_type,
                sub_number=sub_number,
                current_amount=math.ceil(target_amount / (len(valid_emails) + 1)),
                target_amount=target_amount,
                invite_members=",".join(sorted(valid_emails)),
                plan=plan,
                plan_type=plan_type,
                created_by=request.user,
                status="pending",
            )

            # Add creator as owner
            GroupMember.objects.create(
                group=group,
                user=request.user,
                role="owner",
                payment_status="paid",
                locked_amount=math.ceil(target_amount / (len(valid_emails) + 1)),
                paid_amount=target_amount,
            )

            return Response(
                {
                    "success": True,
                    "message": "Group created successfully",
                    "group": {
                        "id": str(group.id),
                        "name": group.name,
                        "description": group.description,
                        "service_type": group.service_type,
                        "target_amount": group.target_amount,
                        "status": group.status,
                        "join_code": group.join_code,
                        "created_at": group.created_at.isoformat(),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AddGroupMemberView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Add member to group",
        description="Add a user to a group (only owner/admin can do this)",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Add Member",
                value={
                    "group_id": 1,
                    "user_email": "member@example.com",
                    "role": "member",
                },
                request_only=True,
            )
        ],
        tags=["Group Payments"],
    )
    def post(self, request):
        try:
            group_id = request.data.get("group_id")
            user_email = request.data.get("user_email")
            role = request.data.get("role", "member")

            group = get_object_or_404(Group, id=group_id)

            # Check if requester is admin/owner
            requester_member = GroupMember.objects.filter(
                group=group, user=request.user, role__in=["owner", "admin"]
            ).first()

            if not requester_member:
                return Response(
                    {"error": "Only group admins can add members"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get user to add
            from accounts.models import Profile

            user_to_add = get_object_or_404(Profile, email=user_email)

            # Check if already a member
            if GroupMember.objects.filter(group=group, user=user_to_add).exists():
                return Response(
                    {"error": "User is already a member of this group"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            group.invite_members = group.invite_members + "," + user_email

            count = GroupMember.objects.filter(
                payment_status="paid", group=group
            ).count()

            invited_emails = group.invite_members.split(",")
            target_amount = group.target_amount

            # Update contribution balance
            group.current_amount = (
                math.ceil(target_amount / (len(invited_emails) + 1)) * count
            )
            group.save()

            return Response(
                {
                    "success": True,
                    "message": f"{user_to_add.email} added to group. Member can now join with group code",
                    "member": {
                        "id": group.id,
                        "email": user_to_add.email,
                        "role": role,
                        "joined_at": member.joined_at,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ListMyGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List my groups",
        description="Get all groups the authenticated user belongs to",
        responses={200: OpenApiTypes.OBJECT},
        tags=["Group Payments"],
    )
    def get(self, request):
        try:
            memberships = GroupMember.objects.filter(user=request.user).select_related(
                "group"
            )
            groups = []
            for membership in memberships:
                group = membership.group
                member_count = GroupMember.objects.filter(group=group).count()
                paid_members = GroupMember.objects.filter(
                    group=group, payment_status="paid"
                ).count()
                pending_members = GroupMember.objects.filter(
                    group=group, payment_status="pending"
                ).count()

                groups.append(
                    {
                        "id": str(group.id),
                        "name": group.name,
                        "description": group.description,
                        "sub_number": group.sub_number,
                        "service_type": group.service_type,
                        "sub_number": group.sub_number,
                        "target_amount": group.target_amount,
                        "current_amount": group.current_amount,
                        "status": group.status,
                        "plan": group.plan,
                        "plan_type": group.plan_type,
                        "my_role": membership.role,
                        "my_payment_status": membership.payment_status,
                        "my_locked_amount": membership.locked_amount,
                        "my_paid_amount": membership.paid_amount,
                        "member_count": member_count,
                        "invite_members": group.invite_members,
                        "paid_members": paid_members,
                        "pending_members": pending_members,
                        "join_code": group.join_code,
                        "created_at": group.created_at.isoformat(),
                    }
                )

            return Response(
                {"success": True, "count": len(groups), "groups": groups},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GroupDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get group details",
        description="Get detailed information about a group including all members",
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=["Group Payments"],
    )
    def get(self, request, group_id):
        try:
            group = get_object_or_404(Group, id=group_id)

            # Check if user is a member
            is_member = GroupMember.objects.filter(
                group=group, user=request.user
            ).exists()

            if not is_member:
                return Response(
                    {"error": "You are not a member of this group"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get all members
            members = GroupMember.objects.filter(group=group).select_related("user")
            member_list = []

            for member in members:
                profile_picture = None
                if member.user.image:
                    profile_picture = member.user.image.url

                member_list.append(
                    {
                        "id": member.id,
                        "email": member.user.email,
                        "name": f"{member.user.surname} {member.user.other_names}",
                        "role": member.role,
                        "joined_at": member.joined_at,
                        "locked_amount": member.locked_amount,
                        "profile_picture": profile_picture,
                    }
                )

            return Response(
                {
                    "success": True,
                    "group": {
                        "id": group.id,
                        "name": group.name,
                        "sub_number": group.sub_number,
                        "description": group.description,
                        "created_at": group.created_at,
                        "member_count": len(member_list),
                        "current_amount": group.current_amount,
                        "total_amount": group.target_amount,
                        "members": member_list,
                        "plan": group.plan,
                        "plan_type": group.plan_type,
                        "invite_members": group.invite_members,
                        "join_code": group.join_code,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            print(e)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpdateGroupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update group details",
        description="Update group sub_number (only owner can do this)",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        tags=["Group Payments"],
    )
    def patch(self, request, group_id):
        try:
            group = get_object_or_404(Group, id=group_id)

            # Check if user is owner
            member = GroupMember.objects.filter(
                group=group, user=request.user, role="owner"
            ).first()

            if not member:
                return Response(
                    {"error": "Only group owner can update details"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Update allowed fields
            sub_number = request.data.get("sub_number")
            if sub_number:
                group.sub_number = sub_number
                group.save()

            return Response(
                {
                    "success": True,
                    "message": "Group updated successfully",
                    "group": {
                        "id": str(group.id),
                        "name": group.name,
                        "sub_number": group.sub_number,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class JoinGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        transaction_pin = request.data.get("transaction_pin")

        if not transaction_pin:
            return Response(
                {"error": "Transaction PIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"error": "Please set your transaction PIN first"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response(
                {"error": "Invalid transaction PIN"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_email = request.user.email
            join_code = request.data.get("join_code")

            if not join_code:
                return Response(
                    {"error": "Join code is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Find group by join code
            try:
                group_obj = Group.objects.get(join_code__iexact=join_code, active=True)
            except Group.DoesNotExist:
                return Response(
                    {"error": "Invalid join code"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Check if already a member
            from accounts.models import Profile

            user_profile = Profile.objects.get(email=user_email)

            if GroupMember.objects.filter(group=group_obj, user=user_profile).exists():
                return Response(
                    {"error": "You are already a member of this group"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if user's email was invited
            invited_emails = (
                group_obj.invite_members.split(",") if group_obj.invite_members else []
            )
            invited_emails = [e.strip().lower() for e in invited_emails]

            if user_email.lower() not in invited_emails:
                return Response(
                    {
                        "error": "You were not invited to this group. Only invited members can join."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            target_amount = group_obj.target_amount

            # Update contribution balance
            group_obj.current_amount += math.ceil(
                target_amount / (len(invited_emails) + 1)
            )
            group_obj.save()

            # Add member

            member = GroupMember.objects.create(
                group=group_obj,
                user=user_profile,
                role="member",
                locked_amount=target_amount / (len(invited_emails) + 1),
                paid_amount=target_amount,
                payment_status="paid",
            )

            return Response(
                {
                    "success": True,
                    "message": f"Successfully joined group '{group_obj.name}'",
                    "group": {
                        "id": str(group_obj.id),
                        "name": group_obj.name,
                        "join_code": group_obj.join_code,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Profile.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeaveGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            group_id = request.data.get("group_id")

            if not group_id:
                return Response(
                    {"error": "Group ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            group = get_object_or_404(Group, id=group_id)

            # Check if user is a member
            member = GroupMember.objects.filter(group=group, user=request.user).first()

            if not member:
                return Response(
                    {"error": "You are not a member of this group"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if member.role == "owner":
                return Response(
                    {
                        "error": "Owner cannot leave the group. Cancel the group instead."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            target_amount = group.target_amount
            invited_emails = group.invite_members.split(",")
            # Update contribution balance
            group.current_amount -= math.ceil(target_amount / (len(invited_emails) + 1))
            group.save()
            # Delete member
            member.delete()

            return Response(
                {"success": True, "message": "Successfully left the group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            group_id = request.data.get("group_id")

            if not group_id:
                return Response(
                    {"error": "Group ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            group = get_object_or_404(Group, id=group_id)

            # Check if user is owner
            member = GroupMember.objects.filter(
                group=group, user=request.user, role="owner"
            ).first()

            if not member:
                return Response(
                    {"error": "Only group owner can cancel the group"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Cancel group
            group.status = "canceled"
            group.active = False
            group.save()

            return Response(
                {"success": True, "message": "Group payment canceled successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
