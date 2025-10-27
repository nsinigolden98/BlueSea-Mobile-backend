from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bluesea_mobile.settings')

app = Celery('bluesea_mobile')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'process-auto-topups-every-5-minutes': {
        'task': 'autotopup.tasks.process_auto_topups',
        'schedule': crontab(minute='*/5'),
    },
}