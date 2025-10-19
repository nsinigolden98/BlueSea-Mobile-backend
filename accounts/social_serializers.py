from rest_framework import serializers


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(
        required=True,
        help_text="Google ID token received from Google OAuth"
    )
    
    def validate_id_token(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError("Invalid Google ID token")
        return value


class AppleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(
        required=True,
        help_text="Apple identity token received from Apple Sign In"
    )
    
    # Optional: Apple sends user data only on first authorization
    user = serializers.JSONField(
        required=False,
        help_text="User data from Apple (only sent on first authorization)"
    )
    
    def validate_id_token(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError("Invalid Apple identity token")
        return value


class SocialAuthResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = serializers.DictField()
    is_new_user = serializers.BooleanField()