from rest_framework import serializers
from .models import MarketPlace

class MarketPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketPlace
        fields = '__all__'
