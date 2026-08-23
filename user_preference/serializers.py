from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import UpdateUserModel

User = get_user_model()


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # Include the fields you want to return
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
        ]


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
