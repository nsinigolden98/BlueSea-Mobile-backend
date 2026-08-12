from rest_framework import serializers
from django.core.validators import RegexValidator

from .models import AffiliateProfile, AffiliateLink, AffiliateSale

name_validator = RegexValidator(
    r"^[A-Za-z0-9]+$",
    "Affiliate name can only contain letters and numbers.",
)


class AffiliateApplySerializer(serializers.Serializer):
    affiliate_name = serializers.CharField(max_length=30, validators=[name_validator])
    facebook = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    instagram = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    twitter = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    tiktok = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    agreement = serializers.BooleanField(required=True)

    def validate_agreement(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must accept the affiliate agreement."
            )
        return value

    def validate_affiliate_name(self, value):
        qs = AffiliateProfile.objects.filter(affiliate_name__iexact=value)
        user = self.context["request"].user
        if qs.exclude(user=user).exists():
            raise serializers.ValidationError(
                "This affiliate name is already taken. Please choose another one."
            )
        return value


class AffiliateStatusSerializer(serializers.ModelSerializer):
    is_approved = serializers.BooleanField(read_only=True)

    class Meta:
        model = AffiliateProfile
        fields = [
            "id",
            "affiliate_name",
            "status",
            "is_approved",
            "commission_rate",
            "facebook",
            "instagram",
            "twitter",
            "tiktok",
            "agreement_accepted",
            "rejected_reason",
            "created_at",
        ]
        read_only_fields = fields


class AffiliateLinkSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.event_title", read_only=True)
    link = serializers.CharField(read_only=True)

    class Meta:
        model = AffiliateLink
        fields = [
            "id",
            "event",
            "event_title",
            "commission_rate",
            "clicks",
            "is_active",
            "link",
            "created_at",
        ]
        read_only_fields = ["id", "clicks", "link", "created_at"]


class AffiliateSaleSerializer(serializers.ModelSerializer):
    affiliate_name = serializers.CharField(
        source="affiliate.affiliate_name", read_only=True
    )
    event_title = serializers.CharField(source="event.event_title", read_only=True)
    buyer_email = serializers.CharField(source="buyer.email", read_only=True)

    class Meta:
        model = AffiliateSale
        fields = [
            "id",
            "affiliate_name",
            "event",
            "event_title",
            "buyer",
            "buyer_email",
            "ticket_count",
            "gross_amount",
            "commission_rate",
            "commission_amount",
            "status",
            "created_at",
            "payable_at",
            "paid_at",
        ]
        read_only_fields = fields


class AffiliateDashboardSerializer(serializers.Serializer):
    total_clicks = serializers.IntegerField()
    total_sales = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    payable_count = serializers.IntegerField()
    paid_count = serializers.IntegerField()
    revoked_count = serializers.IntegerField()
    pending_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payable_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
