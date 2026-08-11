from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import SupportTicket, SupportMessage


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ["id", "sender_name", "message", "is_admin", "created_at"]

    @extend_schema_field(serializers.CharField())
    def get_sender_name(self, obj):
        return f"{obj.sender.surname} {obj.sender.other_names}"


class SupportTicketSerializer(serializers.ModelSerializer):
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "subject",
            "description",
            "status",
            "priority",
            "created_at",
            "updated_at",
            "messages",
        ]


class CreateTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["subject", "description", "priority"]


class AddMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ["message"]


class SupportTicketListResponse(serializers.Serializer):
    count = serializers.IntegerField()
    tickets = SupportTicketSerializer(many=True)


class CreateTicketResponse(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    ticket = SupportTicketSerializer()


class AddMessageResponse(serializers.Serializer):
    success = serializers.BooleanField()
    message = SupportMessageSerializer()
