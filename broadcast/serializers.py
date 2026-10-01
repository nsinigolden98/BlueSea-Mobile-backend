from rest_framework import serializers

from .models import Broadcast


class BroadcastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broadcast
        fields = [
            "id",
            "kind",
            "title",
            "message",
            "email_subject",
            "template",
            "month_key",
            "status",
            "total",
            "sent_count",
            "failed_count",
            "created_by",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total",
            "sent_count",
            "failed_count",
            "created_by",
            "created_at",
            "completed_at",
        ]
