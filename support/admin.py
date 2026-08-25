from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import SupportTicket, SupportMessage, SupportAttachment


def notify_admin_reply(message):
    from notifications.utils import send_notification

    ticket = message.ticket
    send_notification(
        user=ticket.user,
        title="New reply on your support ticket",
        message=(
            f'Support replied to your ticket "{ticket.subject}". '
            "Tap to view the conversation."
        ),
        notification_type="info",
        email_subject="BlueSea Mobile - Support Reply",
    )


class MultipleFileInput(forms.FileInput):
    def __init__(self, attrs=None):
        attrs = dict(attrs or {})
        super().__init__(attrs)
        self.attrs["multiple"] = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data and initial is not None:
            return initial
        if not isinstance(data, (list, tuple)):
            data = [data] if data is not None else []
        result = []
        for item in data:
            if item in (None, ""):
                continue
            result.append(super().clean(item, None))
        return result


class SupportMessageReplyForm(forms.ModelForm):
    images = MultipleImageField(required=False)

    class Meta:
        model = SupportMessage
        fields = ["message"]

    def clean(self):
        cleaned_data = super().clean()
        field = self.fields["images"]
        uploaded: list = []
        if self.files:
            getlist = getattr(self.files, "getlist", None)
            if getlist:
                uploaded = getlist(self.add_prefix("images")) or []
            else:
                single = self.files.get(self.add_prefix("images"))
                uploaded = (
                    single if isinstance(single, list) else ([single] if single else [])
                )
        validated = []
        for f in uploaded:
            validated.extend(field.clean(f))
        cleaned_data["images"] = validated
        return cleaned_data


class SupportAttachmentInline(admin.TabularInline):
    model = SupportAttachment
    extra = 0
    can_delete = True
    readonly_fields = ["uploaded_at", "attachment_preview"]
    fields = ["image", "attachment_preview"]

    @admin.display(description="Preview")
    def attachment_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:80px;" />', obj.image.url
            )
        return "-"


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    form = SupportMessageReplyForm
    extra = 1
    can_delete = False
    readonly_fields = ["sender", "is_admin"]
    fields = ["sender", "is_admin", "message", "images"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "subject",
        "user",
        "status",
        "priority",
        "message_count",
        "created_at",
        "updated_at",
    ]
    list_filter = ["status", "priority", "created_at"]
    search_fields = [
        "subject",
        "description",
        "user__email",
        "user__surname",
        "user__other_names",
    ]
    inlines = [SupportMessageInline]
    list_select_related = ["user"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(message_count=Count("messages"))

    @admin.display(description="Messages", ordering="message_count")
    def message_count(self, obj):
        return obj.message_count


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "ticket",
        "sender",
        "is_admin",
        "message_preview",
        "created_at",
    ]
    list_filter = ["is_admin", "created_at"]
    search_fields = ["message", "sender__email", "ticket__subject"]
    readonly_fields = ["sender", "is_admin", "created_at"]
    inlines = [SupportAttachmentInline]
    date_hierarchy = "created_at"

    @admin.display(description="Message")
    def message_preview(self, obj):
        text = obj.message or ""
        return text[:80] + "..." if len(text) > 80 else text


@admin.register(SupportAttachment)
class SupportAttachmentAdmin(admin.ModelAdmin):
    list_display = ["id", "message", "attachment_preview", "uploaded_at"]
    readonly_fields = ["uploaded_at", "attachment_preview"]
    search_fields = ["message__ticket__subject", "message__message"]

    @admin.display(description="Preview")
    def attachment_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:100px;" />', obj.image.url
            )
        return "-"
