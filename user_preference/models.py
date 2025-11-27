# from django.db import models
# from django.contrib.auth import get_user_model
# 
#Use get_user_model() to handle custom User models
# User = get_user_model()
# 
#Define the acceptable theme choices
# THEME_CHOICES = [
#     ('light', 'Light Mode'),
#     ('dark', 'Dark Mode'),
# ]
# 
# class UserPreference(models.Model):
#     user = models.OneToOneField(
#         User,
#         on_delete=models.CASCADE,
#         primary_key=True
#     )
#   
#     theme_color = models.CharField(
#         max_length=5, # Length of 'light' or 'dark'
#         choices=THEME_CHOICES,
#         default='light', # MANDATORY: All new entries will default to 'light'
#         help_text="User's preferred theme ('light' or 'dark')"
#     )
#   Add other preferences here (e.g., font_size, notifications_on)
# 
#     class Meta:
#         verbose_name_plural = "User Preferences"
# 
#     def __str__(self):
#         return f"Preferences for {self.user.username} (Theme: {self.theme_color})"