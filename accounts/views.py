from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .utils import send_email_verification
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
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
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate, get_user_model
from .models import Profile, EmailVerification, ResetPassword, ResetPasswordValuationToken
from .social_auth import GoogleAuth, AppleAuth, get_or_create_social_user
from .social_serializers import GoogleLoginSerializer, AppleLoginSerializer
import logging
from .serializers import *
import os
from wallet.models import Wallet
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

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
            500: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Registration Request',
                value={
                    "username": "john_doe",
                    "email": "john@example.com",
                    "password": "SecurePassword123",
                    "phone_number": "08012345678",
                    "role": "user"
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    "message": "Account successfully created, check your email",
                    "state": True
                },
                response_only=True
            )
        ],
        tags=['Authentication']
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

                    otp = get_random_string(6, '0123456789')
                    timestamp = timezone.now()

                    verification_url = f"{settings.LOCAL_URL}/accounts/verify-email?code={int(otp)}&email={account.email}"
                    template = "accounts/signup_email_verify.html"

                    send_email = send_email_verification(
                        subject="Verify Email Address",
                        email=account.email,
                        template=template,
                        context={
                            "email": account.email,
                            "verification_code": otp
                        }
                    )
                    
                    if send_email:
                        EmailVerification.objects.update_or_create(
                            email=account.email,
                            defaults={'otp': otp, 'timestamp': timestamp}
                        )
                        return Response(
                            {
                                "message": "Account successfully created, check your email",
                                "state": True
                            },
                            status=status.HTTP_201_CREATED
                        )
                    else:
                        return Response(
                            {
                                "message": "Account created but failed to send verification email",
                                "state": False
                            },
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )   
        except Exception as e:
            print(str(e))
            return Response(
                {
                    "message": "An error occurred during registration",
                    "state": False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyEmail(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Verify email address",
        description="Verify user's email using OTP code sent to their email",
        request=OTPVerificationSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Verification Request',
                value={
                    "email": "john@example.com",
                    "otp": "123456"
                },
                request_only=True
            )
        ],
        tags=['Authentication']
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data["email"]
            user_otp = int(serializer.validated_data["otp"])
            try:
                otp_db = EmailVerification.objects.get(email=email)
            except EmailVerification.DoesNotExist:
                return Response({'message': 'Email not found'}, status=status.HTTP_400_BAD_REQUEST)
            
            if otp_db.timestamp + timedelta(minutes=10) < timezone.now():
                otp_db.delete()
                return Response({'message': 'OTP has expired'}, status=status.HTTP_400_BAD_REQUEST)

            if otp_db.otp == user_otp:
                user = Profile.objects.filter(email = otp_db.email).first()
                if user:
                    user.email_verified = True
                    user.save()
                    otp_db.delete()
                    token = RefreshToken.for_user(user)
                    return Response(
                        data={
                            "message":"Email verified successfully",
                            "state":True,
                            "refresh_token":str(token),
                            "access_token":str(token.access_token)

                            
                        }
                    )
                else:
                    return Response({'message': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'message': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
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
            500: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Resend OTP Request',
                value={"email": "john@example.com"},
                request_only=True
            )
        ],
        tags=['Authentication']
    )
    def post(self, request):

        try:
            email = request.data.get("email")
            if not Profile.objects.filter(email = email).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST, data={
                    "message":"Email does not exist",
                    "state": False
                })
            
            check_user_otp_exists =  EmailVerification.objects.filter(email=email)

            if check_user_otp_exists.exists():
                check_user_otp_exists.delete()
            
            otp = get_random_string(6,'0123456789')
            timestamp = timezone.now()

            send_email = send_email_verification(subject="Veify Email Address",email=email, template="accounts/signup_email_verify.html",context={
                    "email":email,
                    "verification_code":otp
                })
            if send_email:
                    EmailVerification.objects.update_or_create(email=email, defaults={'otp':otp,'timestamp':timestamp})
                    return Response(status=status.HTTP_201_CREATED, data={
                        "message":"Otp successfully sent, check your email",
                        "state":  True
                    })
            else:
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={
                    "message":"Failed to send verification email",
                    "state": False
                })
        except Exception as e:
            print(str(e))
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={
                "message":"An error occured",
                "state": False
            })



class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        refresh = super().get_token(user)
        refresh['role'] = user.role 
        return refresh

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = ProfileSerializer(user).data

        data['access_token'] = data.pop('access')
        data['refresh_token'] = data.pop('refresh')
        return data
    

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(TokenObtainPairView):
    authentication_classes = []
    permission_classes = []
    serializer_class = MyTokenObtainPairSerializer

    @extend_schema(
        summary="User login",
        description="Authenticate user and return JWT tokens",
        request=MyTokenObtainPairSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Login Request',
                value={
                    "username": "john_doe",
                    "password": "SecurePassword123"
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                    "user": {
                        "id": 1,
                        "username": "john_doe",
                        "email": "john@example.com"
                    }
                },
                response_only=True
            )
        ],
        tags=['Authentication']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class GoogleLoginView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Google OAuth login",
        description="Authenticate user using Google OAuth token",
        request=GoogleLoginSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Authentication']
    )
    def post(self, request):
        try:
            serializer = GoogleLoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": "Invalid request data",
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            id_token = serializer.validated_data['id_token']
            
            # Verify Google token
            success, result = GoogleAuth.verify_google_token(id_token)
            
            if not success:
                logger.error(f"Google authentication failed: {result}")
                return Response(
                    {
                        "success": False,
                        "message": "Google authentication failed",
                        "error": result
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get or create user
            user, is_new = get_or_create_social_user('google', result)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['role'] = user.role
            
            # Serialize user data
            user_serializer = ProfileSerializer(user)
            
            logger.info(f"Google login successful for user: {user.email}, New user: {is_new}")
            
            return Response(
                {
                    "success": True,
                    "message": "Login successful" if not is_new else "Account created successfully",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_serializer.data,
                    "is_new_user": is_new
                },
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            logger.error(f"ValueError in Google login: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error in Google login: {str(e)}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "message": "An error occurred during Google login",
                    "error": str(e) if settings.DEBUG else "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AppleLoginView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Apple OAuth login",
        description="Authenticate user using Apple OAuth token",
        request=AppleLoginSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT
        },
        tags=['Authentication']
    )
    def post(self, request):
        try:
            serializer = AppleLoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": "Invalid request data",
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            id_token = serializer.validated_data['id_token']
            user_data_extra = serializer.validated_data.get('user')
            
            # Verify Apple token
            success, result = AppleAuth.verify_apple_token(id_token)
            
            if not success:
                logger.error(f"Apple authentication failed: {result}")
                return Response(
                    {
                        "success": False,
                        "message": "Apple authentication failed",
                        "error": result
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get or create user (pass extra user data for name on first sign-in)
            user, is_new = get_or_create_social_user('apple', result, user_data_extra)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['role'] = user.role
            
            # Serialize user data
            user_serializer = ProfileSerializer(user)
            
            logger.info(f"Apple login successful for user: {user.email}, New user: {is_new}")
            
            return Response(
                {
                    "success": True,
                    "message": "Login successful" if not is_new else "Account created successfully",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_serializer.data,
                    "is_new_user": is_new
                },
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            logger.error(f"ValueError in Apple login: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error in Apple login: {str(e)}", exc_info=True)
            return Response(
                {
                    "success": False,
                    "message": "An error occurred during Apple login",
                    "error": str(e) if settings.DEBUG else "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    
    # @extend_schema(
    #     summary="User logout",
    #     description="Logout user by blacklisting their refresh token",
    #     request=OpenApiTypes.OBJECT,
    #     responses={
    #         200: OpenApiTypes.OBJECT,
    #         400: OpenApiTypes.OBJECT
    #     },
    #     examples=[
    #         OpenApiExample(
    #             'Logout Request',
    #             value={
    #                 "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    #             },
    #             request_only=True
    #         )
    #     ],
    #     tags=['Authentication']
    # )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {
                    "message": "Logout successful",
                    "state": True
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            # logger.error(f"Error during logout: {str(e)}")
            return Response(
                {
                    "message": "Invalid token or logout failed",
                    "state": False
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class PasswordResetView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            serializer = ResetPasswordSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):

                user, code = serializer.save()

                send_mail = send_email_verification(
                    subject="Password Reset Verification Code",
                    template="accounts/password_reset.html",
                    email=user.email,
                    context = {"token": code}
                )

                if send_mail:
                    return Response(
                        {
                            "message":"Password reset OTP sent to your email",
                            "state": True
                        },
                        status=status.HTTP_200_OK
                    )
                return Response(
                    {
                        "message":"Failed to send password reset OTP, try again",
                        "state": False
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            print(str(e))
            return Response(
                {
                    "message":"An error occurred",
                    "state": False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class VerifyResetPasswordOTPView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            serializer = OTPVerificationSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                return Response(
                    {
                        "message":"OTP verified successfully",
                        "state": True
                    },
                    status=status.HTTP_200_OK
                )
        except Exception as e:
            print(str(e))
            return Response(
                {
                    "message":"An error occurred",
                    "state": False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResetPassword(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            token = request.data.get("token")
            new_password = request.data.get("new_password")
            data = signing.loads(token)
            email = data['email']
            user = Profile.objects.get(email=email)
            user.set_password(new_password)

            user.save()
            return Response(
                {
                    "message": "Password Reset Successfully", 
                    "state": True
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            print(str(e))
            return Response(
                {
                    "message": "An error occured",
                    "state": False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )