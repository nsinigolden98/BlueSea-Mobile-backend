from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from .utils import send_email_verification, generate_verification_code, CustomPasswordResetTokenGenerator, gen_simple_token
# from .utils import ResponseHandler
# from .permissions import EmailVerified
from django.contrib.auth.hashers import check_password,make_password
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
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate, get_user_model
from .models import Profile, EmailVerification, ResetPassword, ResetPasswordValuationToken
from .serializers import *
import os

import dotenv

dotenv.load_dotenv()

User = get_user_model()


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                with transaction.atomic():
                    account = serializer.save()
                    role = account.role
                    # account.save()

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

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)