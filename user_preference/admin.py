from django.contrib import admin
from .models import UpdateUserModel


@admin.register(UpdateUserModel)
class UpdateUserModelAdmin(admin.ModelAdmin):
    list_display = ['user', 'image']
    search_fields = ['user__email']
