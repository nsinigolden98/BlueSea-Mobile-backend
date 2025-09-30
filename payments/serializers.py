from rest_framework import serializers
from .models import (
    AirtimeTopUp,
    WAECRegitration,
    WAECResultChecker,
    JAMBRegistration,
    ElectricityPayment,
        )
class AirtimeTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtimeTopUp
        fields= ["amount", "network", "phone_number"]
        read_only_fields= ["id", "created_at"]
        
class ElectricityPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityPayment
        fields= ["billerCode","amount","biller_name","meter_type","phone_number"]
        read_only_fields= ["id","created_at"]
        
class WAECRegitrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAECRegitration
        fields= ["phone_number"]
        read_only_fields= ["id","created_at"] 

class WAECResultCheckerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAECResultChecker
        fields= ["phone_number"]
        read_only_fields= ["id","created_at"] 

class JAMBRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = JAMBRegistration
        fields= ["billerCode","exam_type","phone_number"]
        read_only_fields= ["id","created_at"] 