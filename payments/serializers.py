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
    ElectricityPaymentCustomers,
    Withdrawal
)
# Import your dictionaries from vtpass.py
from .vtpass import mtn_dict, airtel_dict, glo_dict, etisalat_dict 

class AirtimeTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtimeTopUp
        fields= ["amount", "network", "phone_number"]
        read_only_fields= ["id","request_id", "created_at"]



# 1. MTN Serializer
class MTNDataTopUpSerializer(serializers.ModelSerializer):
    # Overriding the model field to allow ID strings (e.g., 'mtn-100')
    plan = serializers.CharField() 

    class Meta:
        model = MTNDataTopUp
        fields = ["plan", "billersCode", "phone_number"]
        read_only_fields = ["id", "request_id", "created_at"]

    def validate_plan(self, value):
        if value not in mtn_dict:
            raise serializers.ValidationError(f"'{value}' is not a valid MTN plan ID.")
        return value

# 2. Airtel Serializer
class AirtelDataTopUpSerializer(serializers.ModelSerializer):
    plan = serializers.CharField()

    class Meta:
        model = AirtelDataTopUp
        fields = ["plan", "billersCode", "phone_number"]
        read_only_fields = ["id", "request_id", "created_at"]

    def validate_plan(self, value):
        if value not in airtel_dict:
            raise serializers.ValidationError(f"'{value}' is not a valid Airtel plan ID.")
        return value

# 3. Glo Serializer
class GloDataTopUpSerializer(serializers.ModelSerializer):
    plan = serializers.CharField()

    class Meta:
        model = GloDataTopUp
        fields = ["plan", "billersCode", "phone_number"]
        read_only_fields = ["id", "request_id", "created_at"]

    def validate_plan(self, value):
        if value not in glo_dict:
            raise serializers.ValidationError(f"'{value}' is not a valid Glo plan ID.")
        return value

# 4. 9mobile (Etisalat) Serializer
class EtisalatDataTopUpSerializer(serializers.ModelSerializer):
    plan = serializers.CharField()

    class Meta:
        model = EtisalatDataTopUp
        fields = ["plan", "billersCode", "phone_number"]
        read_only_fields = ["id", "request_id", "created_at"]

    def validate_plan(self, value):
        if value not in etisalat_dict:
            raise serializers.ValidationError(f"'{value}' is not a valid 9mobile plan ID.")
        return value
        =

class DSTVPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DSTVPayment
        fields= ["billersCode","dstv_plan","subscription_type","phone_number"]
        read_only_fields= ["id","request_id","created_at"]
        
class GOTVPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GOTVPayment
        fields= ["billersCode","gotv_plan","subscription_type","phone_number"]
        read_only_fields= ["id","request_id","created_at"]

class StartimesPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartimesPayment
        fields = ["billersCode","startimes_plan","phone_number"]
        read_only_fields= ["id","request_id","created_at"]
        
class ShowMaxPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowMaxPayment
        fields= ["phone_number","showmax_plan"]
        read_only_fields= ["id","request_id","created_at"]
        
class ElectricityPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityPayment
        fields= ["billerCode","amount","biller_name","meter_type"]
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
        
class ElectricityPaymentCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityPaymentCustomers
        fields = ['meter_type', 'meter_number', 'biller']
        read_only_fields = ['id']

class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = [
            "id",
            "user",
            "account_name",
            "account_number",
            "bank_code",
            "bank_name",
            "amount",
            "status",
            "payment_reference",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "payment_reference",
            "created_at",
            "completed_at",
        ]
