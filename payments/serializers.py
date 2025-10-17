from rest_framework import serializers
from .models import (
    AirtimeTopUp,
    WAECRegitration,
    WAECResultChecker,
    JAMBRegistration,
    ElectricityPayment,
    DSTVPayment,
    GOTVPayment,
    StartimesPayment,
    ShowMaxPayment,
    AirtelDataTopUp,
    GloDataTopUp,
    EtisalatDataTopUp,
    MTNDataTopUp,
    GroupPayment,
    GroupPaymentContribution,
    Airtime2Cash,
)

class AirtimeTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtimeTopUp
        fields= ["amount", "network", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]

class MTNDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = MTNDataTopUp
        fields= ["plan", "billerCode", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]
        
class AirtelDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtelDataTopUp
        fields= ["plan", "billerCode", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]

class GloDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = GloDataTopUp
        fields= ["plan", "billerCode", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]
        
class EtisalatDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtisalatDataTopUp
        fields= ["plan", "billerCode", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]
        
class DSTVPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DSTVPayment
        fields= ["billerCode","dstv_plan","subscription_type","phone_number"]
        read_only_fields= ["id","request_id","created_at"]
        
class GOTVPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GOTVPayment
        fields= ["billerCode","gotv_plan","subscription_type","phone_number"]
        read_only_fields= ["id","request_id","created_at"]

class StartimesPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartimesPayment
        fields= ["billerCode","startimes_plan","phone_number"]
        read_only_fields= ["id","request_id","created_at"]
        
class ShowMaxPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowMaxPayment
        fields= ["phone_number","showmax_plan"]
        read_only_fields= ["id","request_id","created_at"]
        
class ElectricityPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityPayment
        fields= ["billerCode","amount","biller_name","meter_type","phone_number"]
        read_only_fields= ["id","request_id","created_at"]
        
class WAECRegitrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAECRegitration
        fields= ["phone_number"]
        read_only_fields= ["id","request_id","created_at"] 

class WAECResultCheckerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAECResultChecker
        fields= ["phone_number"]
        read_only_fields= ["id","request_id","created_at"] 

class JAMBRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = JAMBRegistration
        fields= ["billerCode","exam_type","phone_number"]
        read_only_fields= ["id","request_id","created_at"] 
        

class GroupPaymentContributionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    member_email = serializers.EmailField(source='member.user.email', read_only=True)

    class Meta:
        model = GroupPaymentContribution
        fields = ['id', 'member_name', 'member_email', 'amount', 'status', 'created_at']

class GroupPaymentSerializer(serializers.ModelSerializer):
    contributions = GroupPaymentContributionSerializer(many=True, read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = GroupPayment
        fields = [
            'id', 'group', 'group_name', 'initiated_by', 'initiated_by_name',
            'payment_type', 'total_amount', 'service_details', 'status',
            'vtu_reference', 'contributions', 'created_at', 'updated_at'
        ]
        

class Airtime2CashSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airtime2Cash
        fields= ["amount", "network", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]