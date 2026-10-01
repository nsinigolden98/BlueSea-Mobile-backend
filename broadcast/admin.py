from django.contrib import admin

from .models import Broadcast


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "title", "status", "total", "sent_count", "failed_count", "month_key", "created_at"]
    list_filter = ["kind", "status", "created_at"]
    search_fields = ["title", "message", "month_key"]
    readonly_fields = ["created_by", "created_at", "completed_at"]
    date_hierarchy = "created_at"
    list_per_page = 30
