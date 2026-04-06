from rest_framework import serializers
from .models import SupportTicket, SupportMessage


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ["id", "sender_name", "message", "is_admin", "created_at"]

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
