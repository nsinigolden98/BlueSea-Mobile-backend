from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from rest_framework import serializers

from .models import Profile


class UserSerializer(serializers.Serializer):
    surname = serializers.CharField()
    other_names = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if Profile.objects.filter(email=value).exists():
            raise ValidationError("Email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = Profile.objects.create_user(
            email=validated_data["email"],
            phone=validated_data["phone"],
            surname=validated_data["surname"],
            other_names=validated_data["other_names"],
        )
        user.set_password(password)
        user.save()

        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("id", "email", "role", "email_verified", "created_on")
        read_only_fields = ("id", "email_verified", "created_on")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)


class EditPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()


class OTPVerificationSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, data):
        email = data.get("email")

        try:
            owner = Profile.objects.get(email=email)
        except Profile.DoesNotExist:
            raise ValidationError("No user found with the provided email and username.")
        self.user = owner
        return data

    def save(self):
        user = getattr(self, "user", None) or Profile.objects.get(
            email=self.validated_data["email"]
        )
        otp = get_random_string(6, "0123456789")
        return user, otp


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(help_text="JWT refresh token to blacklist")


class UserLookupSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Email of the user to look up")


class TransactionPinSerializer(serializers.Serializer):
    pin = serializers.CharField(help_text="4-digit transaction PIN")


class SetTransactionPinSerializer(serializers.Serializer):
    pin = serializers.CharField(help_text="4-digit transaction PIN")
    confirm_pin = serializers.CharField(help_text="Confirm the transaction PIN")


class ChangeTransactionPinSerializer(serializers.Serializer):
    old_pin = serializers.CharField(help_text="Current 4-digit transaction PIN")
    new_pin = serializers.CharField(help_text="New 4-digit transaction PIN")
    confirm_pin = serializers.CharField(help_text="Confirm the new transaction PIN")


class VerifyPinResetOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(help_text="OTP received via email")


class NewTransactionPinSerializer(serializers.Serializer):
    verification_token = serializers.CharField(
        help_text="Token from PIN reset OTP verification"
    )
    new_pin = serializers.CharField(help_text="New 4-digit transaction PIN")
    confirm_pin = serializers.CharField(help_text="Confirm the new transaction PIN")


class ResetPasswordConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Signed token from OTP verification")
    new_password = serializers.CharField(help_text="New password (min 8 characters)")
    confirm_password = serializers.CharField(help_text="Confirm the new password")

class DedicatedVirtualAccountAssignSerializer(serializers.Serializer):
    first_name =serializers.CharField(
                    help_text="First name for Paystack customer"
                )
    last_name = serializers.CharField(
                    help_text="Last name for Paystack customer"
                )
    account_number = serializers.CharField(
                    help_text="Customer personal account number 10 digits (NUBAN) for Paystack validation"
                )
    bank_code =  serializers.CharField(
                    help_text="Bank code 1-7 digits (e.g. 058, 000013) for account validation"
                )
    bvn = serializers.CharField(
                    help_text="RSA-encrypted BVN (11 digits plain after decrypt, frontend encrypted)"
                )
    phone = serializers.CharField(
                    required=False,
                    help_text="Phone required if not in profile (11 digits, e.g. 08012345678)",
                )
