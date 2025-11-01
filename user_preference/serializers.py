from rest_framework import serializers
from .models import UserPreference, THEME_CHOICES

class UserPreferenceSerializer(serializers.ModelSerializer):
    theme_color = serializers.ChoiceField(
        choices=THEME_CHOICES
    )

    class Meta:
        model = UserPreference
        fields = ['theme_color']