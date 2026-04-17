from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bluesea_mobile.settings")

app = Celery("bluesea_mobile")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "process-auto-topups-every-minute": {
        "task": "autotopup.tasks.process_auto_topups",
        "schedule": 60.0,
    },
    "expire-past-event-tickets": {
        "task": "market_place.tasks.expire_past_event_tickets",
        "schedule": crontab(hour=0, minute=0),
    },
    "send-event-reminders": {
        "task": "market_place.tasks.send_event_reminder_notifications",
        "schedule": crontab(hour=9, minute=0),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
