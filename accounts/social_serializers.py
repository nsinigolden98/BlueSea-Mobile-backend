from rest_framework import serializers


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(
        required=False,
        help_text="Google ID token received from client-side Google Sign-In"
    )
    
    authorization_code = serializers.CharField(
        required=False,
        help_text="Authorization code from server-side OAuth flow"
    )
    
    redirect_uri = serializers.CharField(
        required=False,
        help_text="Redirect URI used in OAuth flow (required with authorization_code)"
    )
    
    def validate(self, data):
        """Ensure either id_token or authorization_code is provided"""
        id_token = data.get('id_token')
        authorization_code = data.get('authorization_code')
        
        if not id_token and not authorization_code:
            raise serializers.ValidationError(
                "Either 'id_token' or 'authorization_code' must be provided"
            )
        
        if authorization_code and not data.get('redirect_uri'):
            raise serializers.ValidationError(
                "'redirect_uri' is required when using 'authorization_code'"
            )
        
        return data


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