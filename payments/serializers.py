from rest_framework import serializers
from decimal import Decimal
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

class AirtimeTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtimeTopUp
        fields= ["user", "amount", "network", "phone_number"]
        read_only_fields= ["user", "id","request_id", "created_at"]

class MTNDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = MTNDataTopUp
        fields= ["user", "plan", "billersCode", "phone_number"]
        read_only_fields= ["user", "id","request_id", "created_at"]
        
class AirtelDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirtelDataTopUp
        fields= ["user", "plan", "billersCode", "phone_number"]
        read_only_fields= ["user", "id","request_id", "created_at"]

class GloDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = GloDataTopUp
        fields= ["user", "plan", "billersCode", "phone_number"]
        read_only_fields= ["user", "id","request_id", "created_at"]
        
class EtisalatDataTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtisalatDataTopUp
        fields= ["user", "plan", "billersCode", "phone_number"]
        read_only_fields= ["user", "id","request_id", "created_at"]
        
class DSTVPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DSTVPayment
        fields= ["user", "billersCode","dstv_plan","subscription_type","phone_number"]
        read_only_fields= ["user", "id","request_id","created_at"]
        
class GOTVPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GOTVPayment
        fields= ["user", "billersCode","gotv_plan","subscription_type","phone_number"]
        read_only_fields= ["user", "id","request_id","created_at"]

class StartimesPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartimesPayment
        fields = ["user", "billersCode","startimes_plan","phone_number"]
        read_only_fields= ["user", "id","request_id","created_at"]
        
class ShowMaxPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowMaxPayment
        fields= ["user", "phone_number","showmax_plan"]
        read_only_fields= ["user", "id","request_id","created_at"]
        
class ElectricityPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityPayment
        fields= ["user", "billerCode","amount","biller_name","meter_type"]
        read_only_fields= ["user", "id","request_id","created_at"]
        
class WAECRegitrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAECRegitration
        fields= ["user", "phone_number"]
        read_only_fields= ["user", "id","request_id","created_at"] 

class WAECResultCheckerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAECResultChecker
        fields= ["user", "phone_number"]
        read_only_fields= ["user", "id","request_id","created_at"] 

class JAMBRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = JAMBRegistration
        fields= ["user", "billerCode","exam_type","phone_number"]
        read_only_fields= ["user", "id","request_id","created_at"] 
        

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
        fields= ["user", "amount", "network", "phone_number"]
        read_only_fields= ["user", "id","request_id", "created_at"]
        
class ElectricityPaymentCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectricityPaymentCustomers
        fields = ["user", 'meter_type', 'meter_number', 'biller']
        read_only_fields = ["user", 'id']

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
            "user",
            "status",
            "payment_reference",
            "created_at",
            "completed_at",
        ]

class WithdrawalRequestSerializer(serializers.Serializer):
    account_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=10)
    bank_code = serializers.CharField(max_length=10)
    bank_name = serializers.CharField(max_length=50)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("500.00")
    )
    transaction_pin = serializers.CharField(write_only=True)


class WithdrawalResponseSerializer(serializers.Serializer):
    state = serializers.BooleanField()
    message = serializers.CharField()
    withdrawal = WithdrawalSerializer()
