from rest_framework import serializers
from .models import MarketPlace

class MarketPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketPlace
        fields = ["product_name", "product_description", "image"]
        read_only_fields = ["id", "created_at"]