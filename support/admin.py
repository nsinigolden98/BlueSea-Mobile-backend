from django.contrib import admin

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


class SupportAttachmentInline(admin.TabularInline):
    model = SupportAttachment
    extra = 0
    can_delete = True
    readonly_fields = ["uploaded_at"]


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 1
    can_delete = False
    fields = ["message"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "user", "status", "priority", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = [
        "subject",
        "description",
        "user__email",
        "user__surname",
        "user__other_names",
    ]
    inlines = [SupportMessageInline]
    list_select_related = ["user"]

    def save_formset(self, request, form, formset, change):
        if formset.model is SupportMessage:
            for inline_form in formset.forms:
                if (
                    inline_form.has_changed()
                    and inline_form.instance.pk is None
                    and inline_form.cleaned_data.get("message")
                ):
                    inline_form.instance.sender = request.user
                    inline_form.instance.is_admin = True
        super().save_formset(request, form, formset, change)
        if formset.model is SupportMessage:
            for new_message in formset.new_objects:
                notify_admin_reply(new_message)


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket", "sender", "is_admin", "created_at"]
    list_filter = ["is_admin"]
    search_fields = ["message", "sender__email"]
    readonly_fields = ["sender", "is_admin", "created_at"]
    inlines = [SupportAttachmentInline]


@admin.register(SupportAttachment)
class SupportAttachmentAdmin(admin.ModelAdmin):
    list_display = ["id", "message", "uploaded_at"]
    readonly_fields = ["uploaded_at"]
