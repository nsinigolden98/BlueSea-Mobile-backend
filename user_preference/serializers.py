from rest_framework import serializers
from .models import UserPreference, THEME_CHOICES

class UserPreferenceSerializer(serializers.ModelSerializer):
#     email = serializers.SerializerMethodField(read_only=True)
#     def email(self, obj):
#         return obj.user.email
    theme_color = serializers.ChoiceField(
        choices=THEME_CHOICES
    )

    class Meta:
        model = UserPreference
        fields = ['theme_color']
        #read_only_fields = True
