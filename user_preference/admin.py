from django.contrib import admin
from django.utils.html import format_html

from .models import UpdateUserModel


@admin.register(UpdateUserModel)
class UpdateUserModelAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "nickname",
        "gender",
        "image_thumbnail",
        "date_of_birth",
        "country",
        "state",
        "city",
        "postal_code",
        "updated_on",
    ]
    list_filter = ["gender", "country", "state", "city"]
    search_fields = [
        "user__email",
        "user__phone",
        "nickname",
        "country",
        "state",
        "city",
        "postal_code",
        "street_address",
        "landmark",
    ]
    readonly_fields = ["user", "image_preview", "updated_on"]
    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Profile Image", {"fields": ("image", "image_preview")}),
        (
            "Personal Info",
            {"fields": ("nickname", "gender", "date_of_birth", "updated_on")},
        ),
        (
            "Address",
            {
                "fields": (
                    "country",
                    "state",
                    "city",
                    "street_address",
                    "landmark",
                    "postal_code",
                )
            },
        ),
    )
    date_hierarchy = "date_of_birth"
    list_per_page = 25

    @admin.display(description="Image")
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:50px;height:50px;'
                'object-fit:cover;border-radius:6px;" />',
                obj.image.url,
            )
        return "—"

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:200px;max-height:200px;" />',
                obj.image.url,
            )
        return "No image"
