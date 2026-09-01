from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import UpdateUserModel

User = get_user_model()


class DvaInfoSerializer(serializers.Serializer):
    account_number = serializers.CharField()
    account_name = serializers.CharField()
    bank_name = serializers.CharField()
    bank_slug = serializers.CharField()
    bank_id = serializers.IntegerField(allow_null=True)
    customer_code = serializers.CharField()
    active = serializers.BooleanField()


class CurrentUserSerializer(serializers.ModelSerializer):
    has_DVA = serializers.BooleanField(read_only=True)
    dva_account = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "other_names",
            "email",
            "phone",
            "surname",
            "pin_is_set",
            "image",
            "referral_code",
            "created_on",
            "has_DVA",
            "dva_account",
        ]

    def get_dva_account(self, obj):
        if not getattr(obj, "has_DVA", False):
            return None
        try:
            dva = getattr(obj, "dva_account", None)
            if dva is None:
                from accounts.models import PaystackDedicatedAccount

                dva = PaystackDedicatedAccount.objects.filter(user=obj).first()
            if not dva:
                return None
            return {
                "account_number": dva.account_number,
                "account_name": dva.account_name,
                "bank_name": dva.bank_name,
                "bank_slug": dva.bank_slug,
                "bank_id": dva.bank_id,
                "customer_code": dva.customer_code,
                "active": dva.active,
            }
        except Exception:
            return None


class UpdateUserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UpdateUserModel
        fields = [
            "image",
            "phone",
            "nickname",
            "gender",
            "date_of_birth",
            "country",
            "state",
            "city",
            "street_address",
            "landmark",
            "postal_code",
            "updated_on",
        ]


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UpdateUserModel
        fields = [
            "image",
            "nickname",
            "gender",
            "date_of_birth",
            "country",
            "state",
            "city",
            "street_address",
            "landmark",
            "postal_code",
            "updated_on",
        ]
