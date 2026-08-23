from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    CurrentUserSerializer,
    UpdateUserSerializer,
    UserPreferenceSerializer,
)
from .models import UpdateUserModel
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.models import Profile
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiParameter,
    inline_serializer,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


class CurrentUserView(APIView):
    # Ensure only authenticated users can access this view
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Needed for file uploads

    @extend_schema(
        summary="Get current user profile",
        description=(
            "Return the authenticated user's profile details, "
            "including saved preferences"
        ),
        responses={
            200: inline_serializer(
                name="CurrentUserWithPreference",
                fields={
                    "id": serializers.IntegerField(),
                    "other_names": serializers.CharField(),
                    "email": serializers.EmailField(),
                    "phone": serializers.CharField(allow_null=True),
                    "surname": serializers.CharField(allow_null=True),
                    "pin_is_set": serializers.BooleanField(),
                    "image": serializers.URLField(allow_null=True, required=False),
                    "referral_code": serializers.CharField(allow_null=True),
                    "created_on": serializers.DateTimeField(),
                    "preference": UserPreferenceSerializer(),
                },
            )
        },
        examples=[
            OpenApiExample(
                "Success Response",
                value={
                    "id": 1,
                    "other_names": "John",
                    "email": "user@example.com",
                    "phone": "08012345678",
                    "surname": "Doe",
                    "pin_is_set": True,
                    "image": "http://example.com/media/profiles/photo.jpg",
                    "referral_code": "REF123",
                    "created_on": "2026-01-01T12:00:00Z",
                    "preference": {
                        "image": "http://example.com/media/profiles/photo.jpg",
                        "nickname": "Johnny",
                        "gender": "male",
                        "date_of_birth": "1990-01-01",
                        "country": "Nigeria",
                        "state": "Lagos",
                        "city": "Ikeja",
                        "street_address": "123 Main St",
                        "landmark": "Near Plaza",
                        "postal_code": "100001",
                    },
                },
                response_only=True,
            ),
        ],
        tags=["User Profile"],
    )
    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        data = dict(serializer.data)

        preference, _ = UpdateUserModel.objects.get_or_create(user=request.user)
        data["preference"] = UserPreferenceSerializer(preference).data

        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update current user profile",
        description=(
            "Update the user's phone number and/or profile fields "
            "(nickname, gender, date_of_birth, country, state, city, "
            "street_address, landmark, postal_code) and/or profile image "
            "(multipart/form-data)"
        ),
        request=UpdateUserSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Update Request",
                value={
                    "phone": "08012345678",
                    "image": "<binary file>",
                    "nickname": "Johnny",
                    "gender": "male",
                    "country": "Nigeria",
                    "state": "Lagos",
                    "city": "Ikeja",
                    "street_address": "123 Main St",
                    "landmark": "Near Plaza",
                    "postal_code": "100001",
                    "date_of_birth": "1990-01-01",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "message": "Profile updated successfully",
                    "phone": "08012345678",
                    "image": "http://example.com/media/profiles/photo.jpg",
                    "preference": {
                        "nickname": "Johnny",
                        "gender": "male",
                        "country": "Nigeria",
                        "state": "Lagos",
                        "city": "Ikeja",
                        "street_address": "123 Main St",
                        "landmark": "Near Plaza",
                        "postal_code": "100001",
                        "date_of_birth": "1990-01-01",
                    },
                },
                response_only=True,
            ),
        ],
        tags=["User Profile"],
    )
    def patch(self, request):
        user = request.user

        # Handle phone update separately (updates Profile model)
        phone = request.data.get("phone")
        if phone is not None:
            user.phone = phone
            user.save()

        # Update preference fields on UpdateUserModel
        preference, _ = UpdateUserModel.objects.get_or_create(user=user)
        serializer = UpdateUserSerializer(preference, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

        return Response(
            {
                "message": "Profile updated successfully",
                "phone": user.phone,
                "image": user.image.url if user.image else None,
                "preference": UserPreferenceSerializer(preference).data,
            },
            status=status.HTTP_200_OK,
        )


class CheckUsers(APIView):
    @extend_schema(
        summary="Check user verification status",
        description="Check whether a user with the given email exists and is verified",
        parameters=[
            OpenApiParameter(
                name="email",
                location=OpenApiParameter.PATH,
                required=True,
                description="Email of the user to check",
            ),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Verified",
                value={"state": True, "message": "User is verified"},
                response_only=True,
            ),
            OpenApiExample(
                "Not Verified",
                value={"state": False, "message": "User is not verified"},
                response_only=True,
            ),
        ],
        tags=["User Profile"],
    )
    def get(self, request, email):
        check = Profile.objects.filter(email=email, email_verified=True).first()
        try:
            if check:
                return Response(
                    {"state": True, "message": "User is verified"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"state": False, "message": "User is not verified"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            return Response(
                {"state": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
