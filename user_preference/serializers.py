from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # Include the fields you want to return
        fields = ('id', 'other_names', 'email', 'phone', 'surname', 'pin_is_set',)
        # You can exclude 'password' and other sensitive fields
        