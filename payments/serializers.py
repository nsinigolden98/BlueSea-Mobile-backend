from rest_framework import serializers
from .models import AirtimeTopUp
        
class AirtimeTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtimeTopUp
        fields= ["amount","network","phone_number"]
        read_only_fields= ["id","reference_id"]