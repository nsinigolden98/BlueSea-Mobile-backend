from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from loyalty_market.models import Reward, RedemptionTransaction



@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'points_cost', 'inventory', 'fulfilment_type', 'created_at']
    list_filter = ['category', 'fulfilment_type', 'created_at']
    search_fields = ['title', 'description', 'category']
    readonly_fields = ['id', 'created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'title', 'description', 'category')
        }),
        ('Reward Details', {
            'fields': ('image_url', 'points_cost', 'inventory', 'polarity_score')
        }),
        ('Availability', {
            'fields': ('availability_start', 'availability_end')
        }),
        ('Fulfilment', {
            'fields': ('fulfilment_type',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )


@admin.register(RedemptionTransaction)
class RedemptionTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_link', 'reward_link', 'points_deducted', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'redeemed_at']
    search_fields = ['user_id__username', 'user_id__email', 'reward_id__title']
    readonly_fields = ['id', 'created_at', 'redeemed_at']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'user_id', 'reward_id', 'points_deducted', 'status')
        }),
        ('Fulfilment', {
            'fields': ('fulfilment_payload',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'redeemed_at')
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user_id.id])
        return format_html('<a href="{}">{}</a>', url, obj.user_id.username)
    user_link.short_description = 'User'
    
    def reward_link(self, obj):
        url = reverse('admin:loyalty_market_reward_change', args=[obj.reward_id.id])
        return format_html('<a href="{}">{}</a>', url, obj.reward_id.title)
    reward_link.short_description = 'Reward'


