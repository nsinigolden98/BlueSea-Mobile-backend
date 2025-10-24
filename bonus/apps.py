from django.apps import AppConfig


class BonusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bonus'


# from django.apps import AppConfig


# class BonusConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'bonus'
#     verbose_name = 'Bonus Points System'
    
#     def ready(self):
#         import bonus.signals