from django.core.cache import cache
import random
import uuid
from click import confirm
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from autotopup.views import IsAuthenticated
from transactions.urls import api_view
from .utils import send_email_verification
from rest_framework_simplejwt.views import TokenObtainPairView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.crypto import get_random_string
from django.utils import timezone
from datetime import timedelta
from django.core import signing
from django.conf import settings
from django.db import transaction
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from .models import (
    Profile,
    EmailVerification,
    ResetPassword,
    ResetPasswordValuationToken,
)
from .social_auth import GoogleAuth, AppleAuth, get_or_create_social_user
from .social_serializers import GoogleLoginSerializer, AppleLoginSerializer
from .crypto import decrypt_pin, PinDecryptionError
from .pin_security import verify_pin_with_lockout
import logging
from .serializers import *
import os
import re
import requests
from wallet.models import Wallet
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiParameter,
    inline_serializer,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers

import dotenv

dotenv.load_dotenv()

User = get_user_model()


logger = logging.getLogger(__name__)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Register a new user",
        description="Create a new user account and send email verification",
        request=UserSerializer,
        responses={
            201: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Registration Request",
                value={
                    "surname": "Doe",
                    "other_names": "John",
                    "email": "john@example.com",
                    "phone": "08012345678",
                    "password": "SecurePassword123",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "message": "Account successfully created, check your email",
                    "state": True,
                },
                response_only=True,
            ),
        ],
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                with transaction.atomic():
                    account = serializer.save()
                    role = account.role
                    # account.save()
                    Wallet.objects.create(user=account)

                    otp = get_random_string(6, "0123456789")
                    timestamp = timezone.now()

                    verification_url = f"{settings.LOCAL_URL}/accounts/verify-email?code={int(otp)}&email={account.email}"
                    template = "accounts/signup_email_verify.html"

                    send_email = send_email_verification(
                        subject="Verify Email Address",
                        email=account.email,
                        template=template,
                        context={"email": account.email, "verification_code": otp},
                    )

                    if send_email:
                        EmailVerification.objects.update_or_create(
                            email=account.email,
                            defaults={"otp": otp, "timestamp": timestamp},
                        )
                        return Response(
                            {
                                "message": "Account successfully created, check your email",
                                "state": True,
                            },
                            status=status.HTTP_201_CREATED,
                        )
                    else:
                        return Response(
                            {
                                "message": "Account created but failed to send verification email",
                                "state": False,
                            },
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
        except serializers.ValidationError as e:
            logger.error(f"Validation error during registration: {str(e)}")
            return Response(
                {"message": "Registration Failed", "errors": e.detail, "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            print(str(e))
            logger.error(f"Registration error: {str(e)}")
            return Response(
                {"message": "An error occurred during registration", "state": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyEmail(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Verify email address",
        description="Verify user's email using OTP code sent to their email",
        request=OTPVerificationSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Verification Request",
                value={"email": "john@example.com", "otp": "123456"},
                request_only=True,
            )
        ],
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data["email"]
            user_otp = int(serializer.validated_data["otp"])
            try:
                otp_db = EmailVerification.objects.get(email=email)
            except EmailVerification.DoesNotExist:
                return Response(
                    {"message": "Email not found"}, status=status.HTTP_400_BAD_REQUEST
                )

            if otp_db.timestamp + timedelta(minutes=10) < timezone.now():
                otp_db.delete()
                return Response(
                    {"message": "OTP has expired"}, status=status.HTTP_400_BAD_REQUEST
                )

            if otp_db.otp == user_otp:
                user = Profile.objects.filter(email=otp_db.email).first()
                if user:
                    user.email_verified = True
                    user.save()
                    otp_db.delete()
                    token = RefreshToken.for_user(user)
                    return Response(
                        data={
                            "message": "Email verified successfully",
                            "state": True,
                            "refresh_token": str(token),
                            "access_token": str(token.access_token),
                        }
                    )
                else:
                    return Response(
                        {"message": "User not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOtp(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Resend OTP",
        description="Resend verification OTP to user's email",
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Resend OTP Request",
                value={"email": "john@example.com"},
                request_only=True,
            )
        ],
        tags=["Authentication"],
    )
    def post(self, request):

        try:
            email = request.data.get("email")
            if not Profile.objects.filter(email=email).exists():
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"message": "Email does not exist", "state": False},
                )

            check_user_otp_exists = EmailVerification.objects.filter(email=email)

            if check_user_otp_exists.exists():
                check_user_otp_exists.delete()

            otp = get_random_string(6, "0123456789")
            timestamp = timezone.now()

            send_email = send_email_verification(
                subject="Veify Email Address",
                email=email,
                template="accounts/signup_email_verify.html",
                context={"email": email, "verification_code": otp},
            )
            if send_email:
                EmailVerification.objects.update_or_create(
                    email=email, defaults={"otp": otp, "timestamp": timestamp}
                )
                return Response(
                    status=status.HTTP_201_CREATED,
                    data={
                        "message": "Otp successfully sent, check your email",
                        "state": True,
                    },
                )
            else:
                return Response(
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    data={
                        "message": "Failed to send verification email",
                        "state": False,
                    },
                )
        except Exception as e:
            print(str(e))
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={"message": "An error occured", "state": False},
            )


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        refresh = super().get_token(user)
        refresh["role"] = user.role
        return refresh

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["user"] = ProfileSerializer(user).data

        data["access_token"] = data.pop("access")
        data["refresh_token"] = data.pop("refresh")
        return data


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(TokenObtainPairView):
    authentication_classes = []
    permission_classes = []
    serializer_class = MyTokenObtainPairSerializer

    @extend_schema(
        summary="User login",
        description="Authenticate user and return JWT tokens",
        request=MyTokenObtainPairSerializer,
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Login Request",
                value={"email": "john@example.com", "password": "SecurePassword123"},
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                    "user": {
                        "id": 1,
                        "email": "john@example.com",
                        "role": "user",
                        "email_verified": True,
                    },
                },
                response_only=True,
            ),
        ],
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class GoogleLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Google OAuth login",
        description="Authenticate user using Google OAuth. Supports both ID token (client-side) and authorization code (server-side) flows.",
        request=GoogleLoginSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "ID Token Flow (Client-side)",
                value={"id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."},
                request_only=True,
            ),
            OpenApiExample(
                "Authorization Code Flow (Server-side)",
                value={
                    "authorization_code": "4/0AY0e-g7...",
                    "redirect_uri": "http://localhost:3000/auth/callback",
                },
                request_only=True,
            ),
        ],
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            serializer = GoogleLoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": "Invalid request data",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            id_token_val = serializer.validated_data.get("id_token")
            authorization_code = serializer.validated_data.get("authorization_code")
            redirect_uri = serializer.validated_data.get("redirect_uri")
            phone = serializer.validated_data.get("phone")

            # Determine which flow to use
            if id_token_val:
                # Client-side ID token flow
                success, result = GoogleAuth.verify_google_token(id_token_val)
                flow_type = "ID token"
            elif authorization_code:
                # Server-side authorization code flow
                success, result = GoogleAuth.exchange_code_for_token(
                    authorization_code, redirect_uri
                )
                flow_type = "Authorization code"
            else:
                return Response(
                    {
                        "success": False,
                        "message": "No authentication credentials provided",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not success:
                logger.error(f"Google authentication failed ({flow_type}): {result}")
                return Response(
                    {
                        "success": False,
                        "message": "Google authentication failed",
                        "error": result,
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Get or create user
            extra_data = {"phone": phone} if phone else None
            user, is_new = get_or_create_social_user("google", result, extra_data)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh["role"] = user.role

            # Serialize user data
            user_serializer = ProfileSerializer(user)

            logger.info(
                f"Google login successful ({flow_type}) for user: {user.email}, New user: {is_new}"
            )

            return Response(
                {
                    "success": True,
                    "message": "Login successful"
                    if not is_new
                    else "Account created successfully",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_serializer.data,
                    "is_new_user": is_new,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError as e:
            logger.error(f"ValueError in Google login: {str(e)}")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Unexpected error in Google login: {str(e)}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "message": "An error occurred during Google login",
                    "error": str(e) if settings.DEBUG else "Internal server error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AppleLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Apple OAuth login",
        description="Authenticate user using Apple OAuth token",
        request=AppleLoginSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            serializer = AppleLoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": "Invalid request data",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            id_token = serializer.validated_data["id_token"]
            user_data_extra = serializer.validated_data.get("user")
            phone = serializer.validated_data.get("phone")

            # Add phone to extra_data
            if phone:
                if not user_data_extra:
                    user_data_extra = {}
                user_data_extra["phone"] = phone

            # Verify Apple token
            success, result = AppleAuth.verify_apple_token(id_token)

            if not success:
                logger.error(f"Apple authentication failed: {result}")
                return Response(
                    {
                        "success": False,
                        "message": "Apple authentication failed",
                        "error": result,
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Get or create user (pass extra user data for name on first sign-in)
            user, is_new = get_or_create_social_user("apple", result, user_data_extra)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh["role"] = user.role

            # Serialize user data
            user_serializer = ProfileSerializer(user)

            logger.info(
                f"Apple login successful for user: {user.email}, New user: {is_new}"
            )

            return Response(
                {
                    "success": True,
                    "message": "Login successful"
                    if not is_new
                    else "Account created successfully",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_serializer.data,
                    "is_new_user": is_new,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError as e:
            logger.error(f"ValueError in Apple login: {str(e)}")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Unexpected error in Apple login: {str(e)}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "message": "An error occurred during Apple login",
                    "error": str(e) if settings.DEBUG else "Internal server error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]

    @extend_schema(
        summary="User logout",
        description="Logout user by blacklisting their refresh token",
        request=LogoutSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Logout Request",
                value={"refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."},
                request_only=True,
            )
        ],
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Logout successful", "state": True},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            # logger.error(f"Error during logout: {str(e)}")
            return Response(
                {"message": "Invalid token or logout failed", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PasswordResetView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Request password reset",
        description="Send OTP to user's email for password reset",
        request=ResetPasswordSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            serializer = ResetPasswordSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data["email"]
                user = serializer.user

                otp = get_random_string(6, "0123456789")
                timestamp = timezone.now()

                ResetPassword.objects.update_or_create(
                    profile=user, defaults={"otp": int(otp), "timestamp": timestamp}
                )

                # Send email
                send_mail = send_email_verification(
                    subject="Password Reset Verification Code",
                    template="accounts/password_reset.html",
                    email=user.email,
                    context={"token": otp, "email": user.email},
                )

                if send_mail:
                    return Response(
                        {
                            "message": "Password reset OTP sent to your email",
                            "state": True,
                        },
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {
                        "message": "Failed to send password reset OTP, try again",
                        "state": False,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except Profile.DoesNotExist:
            return Response(
                {
                    "message": "If an account exists with this email, you will receive a reset code",
                    "state": True,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return Response(
                {"message": "An error occurred", "state": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyResetOTPView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Verify password reset OTP",
        description="Verify the OTP and return a token for password reset",
        request=OTPVerificationSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            serializer = OTPVerificationSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data["email"]
                user_otp = serializer.validated_data["otp"]

                try:
                    reset_record = ResetPassword.objects.select_related("profile").get(
                        profile__email=email
                    )
                except (Profile.DoesNotExist, ResetPassword.DoesNotExist):
                    return Response(
                        {"message": "Invalid request", "state": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Check for OTP expiration (10 minutes)
                if reset_record.timestamp + timedelta(minutes=10) < timezone.now():
                    reset_record.delete()
                    return Response(
                        {"message": "OTP has expired", "state": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if reset_record.otp == user_otp:
                    # Generate a secure signed
                    reset_token = signing.dumps(
                        {"email": email, "timestamp": timezone.now().isoformat()},
                        salt="password-reset",
                    )

                    ResetPasswordValuationToken.objects.create(reset_token=reset_token)

                    reset_record.delete()

                    return Response(
                        {
                            "message": "OTP verified successfully",
                            "state": True,
                            "reset_token": reset_token,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"message": "Invalid OTP", "state": False},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except Exception as e:
            logger.error(f"OTP verification error: {str(e)}")
            return Response(
                {"message": "An error occurred", "state": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResetUserPassword(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Reset password",
        description="Reset user password using verified token",
        request=ResetPasswordConfirmSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "Reset Password Request",
                value={
                    "token": "signed_token_from_otp_verification",
                    "new_password": "NewSecurePassword123",
                    "confirm_password": "NewSecurePassword123",
                },
                request_only=True,
            )
        ],
        tags=["Authentication"],
    )
    def post(self, request):
        try:
            token = request.data.get("token")
            new_password = request.data.get("new_password")
            confirm_password = request.data.get("confirm_password")

            if not all([token, new_password, confirm_password]):
                return Response(
                    {"message": "All fields are required", "state": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if confirm_password != new_password:
                return Response(
                    {
                        "message": "New password and confirm password do not match",
                        "state": False,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Add password strength validation
            if len(new_password) < 8:
                return Response(
                    {
                        "message": "Password must be at least 8 characters long",
                        "state": False,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                # Verify token with timeout
                data = signing.loads(token, salt="password-reset", max_age=900)
            except signing.SignatureExpired:
                return Response(
                    {"message": "Reset token has expired", "state": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except signing.BadSignature:
                return Response(
                    {"message": "Invalid reset token", "state": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not ResetPasswordValuationToken.objects.filter(
                reset_token=token
            ).exists():
                return Response(
                    {"message": "Invalid or already used reset token", "state": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email = data["email"]
            user = Profile.objects.get(email=email)
            user.set_password(new_password)
            user.save()

            ResetPasswordValuationToken.objects.filter(reset_token=token).delete()

            ResetPassword.objects.filter(profile=user).delete()

            send_email_verification(
                subject="Password Reset Successful",
                email=user.email,
                template="accounts/password_reset_success.html",
                context={"email": user.email},
            )

            return Response(
                {"message": "Password reset successfully", "state": True},
                status=status.HTTP_200_OK,
            )
        except Profile.DoesNotExist:
            return Response(
                {"message": "User not found", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return Response(
                {"message": "An error occurred", "state": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    summary="Set transaction pin",
    description="Set a 4-digit transaction pin for wallet operation",
    request=SetTransactionPinSerializer,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Set PIN Request",
            value={"pin": "1234", "confirm_pin": "1234"},
            request_only=True,
        )
    ],
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_transaction_pin(request):
    try:
        pin = request.data.get("pin")
        confirm_pin = request.data.get("confirm_pin")

        if not pin or not confirm_pin:
            return Response(
                {"message": "Both pin and confirm_pin are required", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            plain_pin = decrypt_pin(pin)
            plain_confirm = decrypt_pin(confirm_pin)
        except PinDecryptionError:
            return Response(
                {"message": "Invalid transaction pin format", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(plain_pin) != 4 or not plain_pin.isdigit():
            return Response(
                {"message": "Pin must be a 4-digit number", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plain_pin != plain_confirm:
            return Response(
                {"message": "Pin and confirm pin do not match", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.pin_is_set:
            return Response(
                {"message": "Transaction pin is already set", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_transaction_pin(pin)

        return Response(
            {"message": "Transaction pin set successfully", "state": True},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Set transaction pin error: {str(e)}")
        return Response(
            {"message": "An error occurred", "state": False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Change transaction pin",
    description="Change the existing transaction pin",
    request=ChangeTransactionPinSerializer,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Change PIN Request",
            value={"old_pin": "1234", "new_pin": "5678", "confirm_pin": "5678"},
            request_only=True,
        )
    ],
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_transaction_pin(request):

    try:
        old_pin = request.data.get("old_pin")
        new_pin = request.data.get("new_pin")
        confirm_pin = request.data.get("confirm_pin")

        if not all([old_pin, new_pin, confirm_pin]):
            return Response(
                {
                    "message": "Old pin, new pin, and confirm pin are required",
                    "state": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"message": "Transaction pin is not set", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pin_result = verify_pin_with_lockout(request.user, old_pin)
        if pin_result.locked:
            retry_min = int(pin_result.retry_after // 60) + 1
            return Response(
                {
                    "message": f"Too many attempts. Try again in {retry_min} minutes.",
                    "state": False,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if not pin_result.ok:
            return Response(
                {"message": "Old pin is incorrect", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            plain_new = decrypt_pin(new_pin)
            plain_confirm = decrypt_pin(confirm_pin)
        except PinDecryptionError:
            return Response(
                {"message": "Invalid transaction pin format", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(plain_new) != 4 or not plain_new.isdigit():
            return Response(
                {"message": "New pin must be a 4-digit number", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plain_new != plain_confirm:
            return Response(
                {
                    "success": False,
                    "message": "New PINs do not match",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_transaction_pin(new_pin)

        return Response(
            {"message": "Transaction pin changed successfully", "state": True},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Change transaction pin error: {str(e)}")
        return Response(
            {"message": "An error occurred", "state": False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Verify transaction pin",
    description="Verify the user's transaction pin",
    request=TransactionPinSerializer,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Verify PIN Request",
            value={"pin": "1234"},
            request_only=True,
        )
    ],
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_pin(request):

    try:
        pin = request.data.get("pin")

        if not pin:
            return Response(
                {"message": "Pin is required", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.pin_is_set:
            return Response(
                {"message": "Transaction pin is not set", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pin_result = verify_pin_with_lockout(request.user, pin)
        if pin_result.locked:
            retry_min = int(pin_result.retry_after // 60) + 1
            return Response(
                {
                    "message": f"Too many attempts. Try again in {retry_min} minutes.",
                    "state": False,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if pin_result.ok:
            return Response(
                {"message": "Transaction pin verified successfully", "state": True},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"message": "Invalid transaction pin", "state": False},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(f"Verify transaction pin error: {str(e)}")
        return Response(
            {"message": "An error occurred", "state": False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Request transaction PIN reset",
    description="Request OTP to reset forgotten transaction PIN",
    request=OpenApiTypes.OBJECT,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_pin_reset(request):
    try:
        if not request.user.pin_is_set:
            return Response(
                {"message": "Transaction PIN is not set", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp = random.randint(100000, 999999)

        cache_key = f"pin_reset_otp_{request.user.email}"
        cache.set(cache_key, otp, timeout=600)

        send_mail = send_email_verification(
            subject="Transaction Pin Reset Verification Code",
            template="accounts/pin_reset.html",
            email=request.user.email,
            context={"token": otp, "email": request.user.email},
        )

        if send_mail:
            return Response(
                {
                    "message": "Transaction Pin reset OTP sent to your email",
                    "state": True,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "message": "Failed to send transaction pin reset OTP, try again",
                "state": False,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as e:
        logger.error(f"Request PIN reset error: {str(e)}")
        return Response(
            {"message": "An error occurred", "state": False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Verify PIN reset OTP",
    description="Verify OTP sent for transaction PIN reset",
    request=VerifyPinResetOTPSerializer,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Verify OTP Request",
            value={"otp": "123456"},
            request_only=True,
        )
    ],
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_pin_reset_otp(request):
    try:
        otp = request.data.get("otp")

        if not otp:
            return Response(
                {"message": "OTP is required", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"pin_reset_otp_{request.user.email}"
        cached_otp = cache.get(cache_key)

        if not cached_otp:
            return Response(
                {"message": "OTP has expired or is invalid", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if str(cached_otp) != str(otp):
            return Response(
                {"message": "Invalid OTP", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate verification token (valid for 5 minutes)
        verification_token = f"{uuid.uuid4()}"
        token_cache_key = f"pin_reset_token_{request.user.email}"
        cache.set(token_cache_key, verification_token, timeout=300)

        # Delete used OTP
        cache.delete(cache_key)

        logger.info(f"PIN reset OTP verified for {request.user.email}")

        return Response(
            {
                "message": "OTP verified successfully",
                "state": True,
                "verification_token": verification_token,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Verify PIN reset OTP error: {str(e)}")
        return Response(
            {"message": "An error occurred", "state": False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Reset transaction PIN",
    description="Reset transaction PIN with verified token",
    request=NewTransactionPinSerializer,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Reset PIN Request",
            value={
                "verification_token": "token",
                "new_pin": "5678",
                "confirm_pin": "5678",
            },
            request_only=True,
        )
    ],
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reset_transaction_pin(request):
    try:
        verification_token = request.data.get("verification_token")
        new_pin = request.data.get("new_pin")
        confirm_pin = request.data.get("confirm_pin")

        if not all([verification_token, new_pin, confirm_pin]):
            return Response(
                {
                    "message": "Verification token, new PIN, and confirm PIN are required",
                    "state": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_cache_key = f"pin_reset_token_{request.user.email}"
        cached_token = cache.get(token_cache_key)

        if not cached_token or cached_token != verification_token:
            return Response(
                {"message": "Invalid or expired verification token", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            plain_new = decrypt_pin(new_pin)
            plain_confirm = decrypt_pin(confirm_pin)
        except PinDecryptionError:
            return Response(
                {"message": "Invalid transaction pin format", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(plain_new) != 4 or not plain_new.isdigit():
            return Response(
                {"message": "PIN must be a 4-digit number", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plain_new != plain_confirm:
            return Response(
                {"message": "PINs do not match", "state": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set new PIN
        request.user.set_transaction_pin(new_pin)

        cache.delete(token_cache_key)

        logger.info(f"Transaction PIN reset successfully for {request.user.email}")

        return Response(
            {"message": "Transaction PIN reset successfully", "state": True},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Reset transaction PIN error: {str(e)}")
        return Response(
            {"message": "An error occurred", "state": False},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class LookupUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Lookup user by email",
        description="Look up a user's public profile details by email",
        request=UserLookupSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Lookup Request",
                value={"email": "john@example.com"},
                request_only=True,
            )
        ],
        tags=["Authentication"],
    )
    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.only("email", "other_names", "surname", "image").get(
                email=email
            )
            return Response(
                {
                    "found": True,
                    "email": user.email,
                    "name": f"{user.other_names} {user.surname}",
                    "image": user.image.url if user.image else None,
                }
            )
        except User.DoesNotExist:
            return Response(
                {"found": False, "error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class DedicatedVirtualAccountAssignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Assign Wema Dedicated Virtual Account",
        description="Create single-step Paystack DVA for Wema Bank. BVN is required (frontend sends RSA-encrypted, backend decrypts). Phone is required if not in DB and will update profile. If DVA already exists, returns existing account without creating new one. Handles Paystack responses per docs.",
        request=inline_serializer(
            name="DVAAssignRequest",
            fields={
                "phone": serializers.CharField(
                    required=False,
                    help_text="Phone required if not in profile (11 digits, e.g. 08012345678)",
                ),
                "bvn": serializers.CharField(
                    required=True,
                    help_text="RSA-encrypted BVN (11 digits plain after decrypt, frontend encrypted)",
                ),
            },
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            201: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        tags=["Account"],
        examples=[
            OpenApiExample(
                "Assign Request",
                value={"phone": "08012345678", "bvn": "encrypted_string"},
                request_only=True,
            ),
            OpenApiExample(
                "Existing DVA",
                value={
                    "already_exists": True,
                    "account_number": "0123456789",
                    "account_name": "Test / User",
                    "bank_name": "Wema Bank",
                    "bank_slug": "wema-bank",
                    "customer_code": "CUS_xxx",
                    "has_DVA": True,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Created DVA",
                value={
                    "status": True,
                    "message": "Dedicated account assigned",
                    "data": {
                        "account_number": "9930000001",
                        "account_name": "Bluesea/User",
                        "bank": {"name": "Wema Bank", "slug": "wema-bank"},
                    },
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        from .models import PaystackDedicatedAccount

        user = request.user

        # Idempotent: if DVA already exists, return existing without creating new
        existing = PaystackDedicatedAccount.objects.filter(user=user).first()
        if existing:
            if not user.has_DVA:
                user.has_DVA = True
                user.save(update_fields=["has_DVA"])
            return Response(
                {
                    "already_exists": True,
                    "account_number": existing.account_number,
                    "account_name": existing.account_name,
                    "bank_name": existing.bank_name,
                    "bank_slug": existing.bank_slug,
                    "bank_id": existing.bank_id,
                    "customer_code": existing.customer_code,
                    "active": existing.active,
                    "has_DVA": True,
                },
                status=status.HTTP_200_OK,
            )

        # Phone handling: required if not in DB, and update phone field
        bvn_encrypted = request.data.get("bvn")
        if not bvn_encrypted:
            return Response(
                {"error": "bvn is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            bvn_plain = decrypt_pin(bvn_encrypted)
        except PinDecryptionError:
            return Response(
                {"error": "Invalid encrypted bvn"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {"error": "Invalid encrypted bvn"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not re.match(r"^\d{11}$", bvn_plain or ""):
            return Response(
                {"error": "bvn must be 11 digits"}, status=status.HTTP_400_BAD_REQUEST
            )

        phone_from_request = request.data.get("phone")
        phone_in_db = (user.phone or "").strip() if getattr(user, "phone", None) else ""
        phone_to_use = (phone_from_request or phone_in_db or "").strip()
        if not phone_to_use:
            return Response(
                {"error": "phone is required to create dedicated account"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not re.match(r"^0[789][01]\d{8}$", phone_to_use) and not re.match(
            r"^\+234[789][01]\d{8}$", phone_to_use
        ):
            # Allow +234 or 0 prefix, 11 digits total for 0 prefix
            if not re.match(r"^\d{11}$", phone_to_use):
                return Response(
                    {"error": "phone must be valid Nigerian number (e.g. 08012345678)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update phone field if provided and different or missing in DB
        if phone_from_request and phone_from_request.strip() != phone_in_db:
            try:
                user.phone = phone_from_request.strip()
                user.save(update_fields=["phone"])
            except Exception:
                pass

        # Prepare Paystack single-step payload: wema-bank hard-coded, do not allow frontend to change
        first_name = (
            user.surname or user.other_names or user.email.split("@")[0] or "User"
        ).strip()
        # Paystack expects first_name/last_name separate; use other_names as last_name if available
        last_name = (user.other_names or user.surname or "User").strip()
        if not first_name:
            first_name = user.email.split("@")[0]
        if not last_name:
            last_name = "User"
        # Normalize phone to +234 format for Paystack if needed, but Paystack accepts 080... or +234...
        paystack_phone = phone_to_use
        if paystack_phone.startswith("0"):
            paystack_phone = "+234" + paystack_phone[1:]

        payload = {
            "email": user.email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": paystack_phone,
            "preferred_bank": "wema-bank",
            "country": "NG",
            "bvn": bvn_plain,
        }

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                "https://api.paystack.co/dedicated_account/assign",
                headers=headers,
                json=payload,
                timeout=(3, 10),
            )
        except requests.RequestException as e:
            logger.error(f"Paystack DVA assign network error for {user.email}: {e}")
            return Response(
                {"error": "Unable to contact Paystack, try again"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            j = resp.json()
        except Exception:
            logger.error(
                f"Paystack DVA assign non-JSON response for {user.email}: {resp.text[:500]}"
            )
            return Response(
                {"error": "Invalid response from Paystack"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Handle Paystack responses per docs: https://paystack.com/docs/api/dedicated-virtual-account/#assign
        # Success: status true, message "Dedicated account assigned" or similar, data: {account_number, account_name, bank: {name, slug, id}, active, id, customer: {id, customer_code}, ...}
        # For validation businesses, Paystack may return status true but webhook will confirm via customeridentification.success / dedicatedaccount.assign.success
        # Failure: status false, message contains reason (e.g., "BVN is incorrect", "Customer already has DVA", etc.)
        status_ok = j.get("status") is True
        message = j.get("message", "")
        data = j.get("data") or {}

        if not status_ok:
            # Paystack docs: failure could be due to bvn, phone, etc.
            err_msg = (
                message or j.get("message") or "Failed to assign dedicated account"
            )
            # If Paystack says customer already has DVA, treat as existing and fetch
            if "already" in err_msg.lower() and "assigned" in err_msg.lower():
                # Try to fetch existing DVA via customer
                try:
                    # Attempt to fetch via Paystack dedicated_account list for this customer
                    fetch_headers = {
                        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
                    }
                    cust_code = (
                        data.get("customer_code")
                        or data.get("customer", {}).get("customer_code")
                        if isinstance(data.get("customer"), dict)
                        else None
                    )
                    # Fallback: try to list dedicated accounts for user
                    list_resp = requests.get(
                        f"https://api.paystack.co/dedicated_account?customer={cust_code}"
                        if cust_code
                        else "https://api.paystack.co/dedicated_account",
                        headers=fetch_headers,
                        timeout=(3, 10),
                    )
                    lj = list_resp.json()
                    if lj.get("status") and lj.get("data"):
                        lst = (
                            lj["data"] if isinstance(lj["data"], list) else [lj["data"]]
                        )
                        if lst:
                            d = lst[0]
                            # Create local record from fetched data
                            with transaction.atomic():
                                dva, created = (
                                    PaystackDedicatedAccount.objects.get_or_create(
                                        user=user,
                                        defaults={
                                            "dedicated_account_id": d.get("id"),
                                            "account_number": d.get("account_number"),
                                            "account_name": d.get(
                                                "account_name",
                                                f"{first_name} {last_name}",
                                            ),
                                            "bank_name": d.get("bank", {}).get(
                                                "name", "Wema Bank"
                                            )
                                            if isinstance(d.get("bank"), dict)
                                            else "Wema Bank",
                                            "bank_slug": d.get("bank", {}).get(
                                                "slug", "wema-bank"
                                            )
                                            if isinstance(d.get("bank"), dict)
                                            else "wema-bank",
                                            "bank_id": d.get("bank", {}).get("id")
                                            if isinstance(d.get("bank"), dict)
                                            else None,
                                            "customer_code": d.get("customer", {}).get(
                                                "customer_code", ""
                                            )
                                            if isinstance(d.get("customer"), dict)
                                            else (d.get("customer_code") or ""),
                                            "customer_id": d.get("customer", {}).get(
                                                "id"
                                            )
                                            if isinstance(d.get("customer"), dict)
                                            else None,
                                            "phone": phone_to_use,
                                            "bvn_encrypted": bvn_encrypted,
                                            "active": d.get("active", True),
                                            "paystack_response": d,
                                        },
                                    )
                                )
                                if not user.has_DVA:
                                    user.has_DVA = True
                                    user.save(update_fields=["has_DVA"])
                                return Response(
                                    {
                                        "already_exists": True,
                                        "account_number": dva.account_number,
                                        "account_name": dva.account_name,
                                        "bank_name": dva.bank_name,
                                        "bank_slug": dva.bank_slug,
                                        "customer_code": dva.customer_code,
                                        "has_DVA": True,
                                    },
                                    status=status.HTTP_200_OK,
                                )
                except Exception as e:
                    logger.warning(f"DVA fetch fallback failed for {user.email}: {e}")
            logger.warning(f"Paystack DVA assign failed for {user.email}: {j}")
            return Response(
                {
                    "error": err_msg,
                    "paystack_message": message,
                    "paystack_status": j.get("status"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Success per docs: create local DVA record and set has_DVA true
        try:
            # Paystack success data shape per docs: https://paystack.com/docs/api/dedicated-virtual-account/
            # data: {account_number, account_name, bank: {name, slug, id}, id, active, customer: {id, customer_code, ...}, ...}
            account_number = data.get("account_number")
            account_name = data.get("account_name") or f"{first_name} {last_name}"
            bank_info = data.get("bank") or {}
            bank_name = (
                bank_info.get("name", "Wema Bank")
                if isinstance(bank_info, dict)
                else "Wema Bank"
            )
            bank_slug = (
                bank_info.get("slug", "wema-bank")
                if isinstance(bank_info, dict)
                else "wema-bank"
            )
            bank_id = bank_info.get("id")
            cust = data.get("customer") or {}
            customer_code = (
                cust.get("customer_code")
                if isinstance(cust, dict)
                else data.get("customer_code") or ""
            )
            customer_id = (
                cust.get("id") if isinstance(cust, dict) else data.get("customer_id")
            )
            dedicated_id = data.get("id")
            active = data.get("active", True)

            if not account_number:
                # Some Paystack flows return data with dedicated_account nested
                dedicated = data.get("dedicated_account") or {}
                if isinstance(dedicated, dict) and dedicated.get("account_number"):
                    account_number = dedicated.get("account_number")
                    account_name = dedicated.get("account_name", account_name)
                    bank_info = dedicated.get("bank", bank_info)
                    bank_name = (
                        bank_info.get("name", bank_name)
                        if isinstance(bank_info, dict)
                        else bank_name
                    )
                    bank_slug = (
                        bank_info.get("slug", bank_slug)
                        if isinstance(bank_info, dict)
                        else bank_slug
                    )
                    bank_id = (
                        bank_info.get("id", bank_id)
                        if isinstance(bank_info, dict)
                        else bank_id
                    )
                    dedicated_id = dedicated.get("id", dedicated_id)
                    active = dedicated.get("active", active)

            if not account_number or not customer_code:
                logger.warning(
                    f"Paystack DVA assign success but missing fields for {user.email}: {j}"
                )
                # Still set has_DVA if Paystack says success, but return Paystack data
                return Response(
                    {
                        "status": j.get("status"),
                        "message": message,
                        "data": data,
                        "has_DVA": False,
                    },
                    status=status.HTTP_200_OK,
                )

            with transaction.atomic():
                dva, created = PaystackDedicatedAccount.objects.get_or_create(
                    user=user,
                    defaults={
                        "dedicated_account_id": dedicated_id,
                        "account_number": account_number,
                        "account_name": account_name,
                        "bank_name": bank_name,
                        "bank_slug": bank_slug,
                        "bank_id": bank_id,
                        "customer_code": customer_code,
                        "customer_id": customer_id,
                        "phone": phone_to_use,
                        "bvn_encrypted": bvn_encrypted,
                        "active": active,
                        "paystack_response": j,
                    },
                )
                if not created:
                    # Update existing with latest Paystack data
                    dva.account_number = account_number
                    dva.account_name = account_name
                    dva.bank_name = bank_name
                    dva.bank_slug = bank_slug
                    dva.bank_id = bank_id
                    dva.customer_code = customer_code
                    dva.customer_id = customer_id
                    dva.phone = phone_to_use
                    dva.bvn_encrypted = bvn_encrypted
                    dva.active = active
                    dva.paystack_response = j
                    dva.save()

                if not user.has_DVA:
                    user.has_DVA = True
                    user.save(update_fields=["has_DVA"])

                # Notify user of successful DVA assignment per Paystack docs handling
                try:
                    from notifications.utils import send_notification

                    send_notification(
                        user=user,
                        title="Dedicated Virtual Account Ready",
                        message=f"Your Wema DVA {dva.account_number} ({dva.account_name}) is active and ready to receive transfers.",
                        notification_type="dva_assigned",
                        email_subject="BlueSea - Your Dedicated Account is Ready",
                    )
                except Exception as e:
                    logger.warning(f"DVA assign notify failed {user.email}: {e}")

            # Return per Paystack docs: status, message, data
            return Response(
                {
                    "status": j.get("status"),
                    "message": message,
                    "data": {
                        "account_number": dva.account_number,
                        "account_name": dva.account_name,
                        "bank": {
                            "name": dva.bank_name,
                            "slug": dva.bank_slug,
                            "id": dva.bank_id,
                        },
                        "customer_code": dva.customer_code,
                        "active": dva.active,
                        "has_DVA": True,
                    },
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"DVA local save failed for {user.email}: {e}", exc_info=True)
            return Response(
                {
                    "error": "Failed to save dedicated account",
                    "paystack_message": message,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
