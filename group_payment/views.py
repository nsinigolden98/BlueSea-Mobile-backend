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
                'Create Group',
                value={
                    "name": "Family Group",
                    "description": "Group for family bill payments"
                },
                request_only=True
            )
        ],
        tags=['Group Payments']
    )
    def post(self, request):
        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            name = request.data.get('name')
            description = request.data.get('description', '')
            service_type =request.data.get('service_type')
            sub_number =request.data.get('sub_number')
            target_amount =request.data.get('target_amount')
            invite_members =request.data.get('invite_members')
            plan =request.data.get('plan')
            plan_type =request.data.get('plan_type','')
            join_code =request.data.get('join_code')

            if not name:
                return Response(
                    {'error': 'Group name is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            group = Group.objects.create(
                name=name,
                description=description,
                service_type=service_type,
                sub_number= sub_number,
                target_amount= target_amount,
                invite_members= invite_members,
                plan= plan,
                plan_type= plan_type,
                join_code = join_code,
                created_by=request.user
            )

            # Add creator as owner
            GroupMember.objects.create(
                group=group,
                user=request.user,
                role='owner'
            )

            return Response({
                'success': True,
                'message': 'Group created successfully',
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                    'created_at': group.created_at
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
           # print(str(e))
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
                'Add Member',
                value={
                    "group_id": 1,
                    "user_email": "member@example.com",
                    "role": "member"
                },
                request_only=True
            )
        ],
        tags=['Group Payments']
    )
    def post(self, request):
        try:
            group_id = request.data.get('group_id')
            user_email = request.data.get('user_email')
            role = request.data.get('role', 'member')

            group = get_object_or_404(Group, id=group_id)

            # Check if requester is admin/owner
            requester_member = GroupMember.objects.filter(
                group=group,
                user=request.user,
                role__in=['owner', 'admin']
            ).first()

            if not requester_member:
                return Response(
                    {'error': 'Only group admins can add members'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get user to add
            from accounts.models import Profile
            user_to_add = get_object_or_404(Profile, email=user_email)

            # Check if already a member
            if GroupMember.objects.filter(group=group, user=user_to_add).exists():
                return Response(
                    {'error': 'User is already a member of this group'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Add member
            member = GroupMember.objects.create(
                group=group,
                user=user_to_add,
                role=role
            )

            return Response({
                'success': True,
                'message': f'{user_to_add.email} added to group',
                'member': {
                    'id': member.id,
                    'email': user_to_add.email,
                    'role': member.role,
                    'joined_at': member.joined_at
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ListMyGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List my groups",
        description="Get all groups the authenticated user belongs to",
        responses={200: OpenApiTypes.OBJECT},
        tags=['Group Payments']
    )
    def get(self, request):
        try:
            memberships = GroupMember.objects.filter(user=request.user).select_related('group')
            
            groups = []
            for membership in memberships:
                group = membership.group
                member_count = GroupMember.objects.filter(group=group).count()
                
                groups.append({
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                    'my_role': membership.role,
                    'member_count': member_count,
                    'created_at': group.created_at
                })

            return Response({
                'success': True,
                'count': len(groups),
                'groups': groups
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GroupDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get group details",
        description="Get detailed information about a group including all members",
        responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        tags=['Group Payments']
    )
    def get(self, request, group_id):
        try:
            group = get_object_or_404(Group, id=group_id)

            # Check if user is a member
            is_member = GroupMember.objects.filter(
                group=group,
                user=request.user
            ).exists()

            if not is_member:
                return Response(
                    {'error': 'You are not a member of this group'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get all members
            members = GroupMember.objects.filter(group=group).select_related('user')
            member_list = []
            
            for member in members:
                member_list.append({
                    'id': member.id,
                    'email': member.user.email,
                    'name': f"{member.user.surname} {member.user.other_names}",
                    'role': member.role,
                    'joined_at': member.joined_at
                })

            return Response({
                'success': True,
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                    'created_at': group.created_at,
                    'member_count': len(member_list),
                    'members': member_list
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class JoinGroupView(APIView):
    permission_class =[IsAuthenticated]
    
    def post(self, request):
        
        transaction_pin = request.data.get('transaction_pin')

        if not transaction_pin:
            return Response({'error': 'Transaction PIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.pin_is_set:
            return Response({'error': 'Please set your transaction PIN first'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.verify_transaction_pin(transaction_pin):
            return Response({'error': 'Invalid transaction PIN'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user_email = request.user.email
            join_code = request.data.get('join_code')
            
            check_membership = Group.filter(join_code=join_code, invite_memebers__iexact = user_email, status= 'active').exists()
            
            if check_membership:
                
                group_id = request.data.get('group_id')
                
                role = request.data.get('role', 'member')
    
                group = get_object_or_404(Group, id=group_id)
    
                # Get user to add
                from accounts.models import Profile
                user_to_add = get_object_or_404(Profile, email=user_email)
    
                # Check if already a member
                if GroupMember.objects.filter(group=group, user=user_to_add).exists():
                    return Response(
                        {'error': 'User is already a member of this group'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
    
                # Add member
                member = GroupMember.objects.create(
                    group=group,
                    user=user_to_add,
                    role=role
                )
    
                return Response({
                    'success': True,
                    'message': f'{user_to_add.email} added to group',
                    'member': {
                        'id': member.id,
                        'email': user_to_add.email,
                        'role': member.role,
                        'joined_at': member.joined_at
                    }
                }, status=status.HTTP_200_OK)

                
            else:
                return Response({'success':False,
                    'message': 'Invalid Code Or Not Added To Group Payment'})
                    
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        
        