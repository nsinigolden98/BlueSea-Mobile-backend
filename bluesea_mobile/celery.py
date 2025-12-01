from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bluesea_mobile.settings')

app = Celery('bluesea_mobile')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'process-auto-topups-every-minute': {
        'task': 'autotopup.tasks.process_auto_topups',
        'schedule': 60.0,
    },

    'cleanup-expired-fundings-daily': {
        'task': 'transactions.tasks.clean_pending_fundings',
        'schedule': crontab(hour=2, minute=0),
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')