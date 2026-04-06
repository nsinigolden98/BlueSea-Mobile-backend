from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import CurrentUserSerializer, UpdateUserSerializer
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.models import Profile


class CurrentUserView(APIView):
    # Ensure only authenticated users can access this view
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Needed for file uploads

    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
