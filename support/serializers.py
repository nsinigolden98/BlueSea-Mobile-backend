from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from .models import SupportTicket, SupportMessage, SupportAttachment


@extend_schema_field(OpenApiTypes.BINARY)
class BinaryImageField(serializers.ImageField):
    pass


class SupportAttachmentSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = SupportAttachment
        fields = ["id", "image", "uploaded_at"]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    attachments = SupportAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = SupportMessage
        fields = [
            "id",
            "sender_name",
            "message",
            "is_admin",
            "created_at",
            "attachments",
        ]

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
    images = serializers.ListField(
        child=BinaryImageField(), required=False, write_only=True
    )

    class Meta:
        model = SupportTicket
        fields = ["subject", "description", "priority", "images"]

    def create(self, validated_data):
        validated_data.pop("images", None)
        return super().create(validated_data)


class AddMessageSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=BinaryImageField(), required=False, write_only=True
    )

    class Meta:
        model = SupportMessage
        fields = ["message", "images"]

    def create(self, validated_data):
        validated_data.pop("images", None)
        return super().create(validated_data)


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


class AdminMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    attachments = SupportAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = SupportMessage
        fields = [
            "id",
            "sender_name",
            "message",
            "is_admin",
            "created_at",
            "attachments",
        ]

    @extend_schema_field(serializers.CharField())
    def get_sender_name(self, obj):
        return f"{obj.sender.surname} {obj.sender.other_names}"


class AdminTicketSerializer(serializers.ModelSerializer):
    messages = AdminMessageSerializer(many=True, read_only=True)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    message_count = serializers.IntegerField(read_only=True)

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
            "user_name",
            "user_email",
            "message_count",
        ]
        read_only_fields = ["created_at", "updated_at", "messages", "message_count"]

    @extend_schema_field(serializers.CharField())
    def get_user_name(self, obj):
        return f"{obj.user.surname} {obj.user.other_names}"

    @extend_schema_field(serializers.EmailField())
    def get_user_email(self, obj):
        return obj.user.user.email


class AdminTicketUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=SupportTicket.STATUS_CHOICES, required=False
    )
    priority = serializers.ChoiceField(
        choices=SupportTicket.PRIORITY_CHOICES, required=False
    )
