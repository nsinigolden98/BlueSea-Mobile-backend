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
        ]


class UpdateUserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UpdateUserModel
        fields = ["image", "phone"]
