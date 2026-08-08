from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import CurrentUserSerializer, UpdateUserSerializer
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.models import Profile
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class CurrentUserView(APIView):
    # Ensure only authenticated users can access this view
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Needed for file uploads

    @extend_schema(
        summary="Get current user profile",
        description="Return the authenticated user's profile details",
        responses={200: CurrentUserSerializer},
        tags=["User Profile"],
    )
    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update current user profile",
        description="Update the user's phone number and/or profile image (multipart/form-data)",
        request=UpdateUserSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Update Request",
                value={"phone": "08012345678", "image": "<binary file>"},
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "message": "Profile updated successfully",
                    "phone": "08012345678",
                    "image": "http://example.com/media/profiles/photo.jpg",
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

        # Handle image update (uses UpdateUserSerializer)
        image_data = {k: v for k, v in request.data.items() if k == "image"}

        if image_data:
            serializer = UpdateUserSerializer(user, data=image_data, partial=True)
            if serializer.is_valid():
                serializer.save()

        return Response(
            {
                "message": "Profile updated successfully",
                "phone": user.phone,
                "image": user.image.url if user.image else None,
            },
            status=status.HTTP_200_OK,
        )


class CheckUsers(APIView):
    @extend_schema(
        summary="Check user verification status",
        description="Check whether a user with the given email exists and is verified",
        parameters=[
            OpenApiParameter(name="email", location=OpenApiParameter.PATH, required=True, description="Email of the user to check"),
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
