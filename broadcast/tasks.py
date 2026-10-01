import logging

from celery import Task, shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _maybe_complete(broadcast_id):
    from broadcast.models import Broadcast

    try:
        with transaction.atomic():
            broadcast = Broadcast.objects.select_for_update().get(id=broadcast_id)
            if broadcast.completed_at is not None:
                return
            if broadcast.sent_count + broadcast.failed_count < broadcast.total:
                return
            if broadcast.failed_count == 0:
                broadcast.status = "sent"
            elif broadcast.sent_count == 0:
                broadcast.status = "failed"
            else:
                broadcast.status = "partial"
            broadcast.completed_at = timezone.now()
            broadcast.save(update_fields=["status", "completed_at"])
    except Exception as e:
        logger.warning(f"Broadcast {broadcast_id} completion check failed: {e}")


class BroadcastEmailTask(Task):
    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = 60
    retry_jitter = True

    def on_success(self, retval, task_id, args, kwargs):
        from broadcast.models import Broadcast

        broadcast_id = kwargs.get("broadcast_id") if kwargs else None
        if broadcast_id is None and args:
            broadcast_id = args[0]
        Broadcast.objects.filter(id=broadcast_id).update(sent_count=F("sent_count") + 1)
        _maybe_complete(broadcast_id)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        from broadcast.models import Broadcast

        broadcast_id = kwargs.get("broadcast_id") if kwargs else None
        if broadcast_id is None and args:
            broadcast_id = args[0]
        logger.error(f"Broadcast {broadcast_id} email failed: {exc}")
        Broadcast.objects.filter(id=broadcast_id).update(
            failed_count=F("failed_count") + 1
        )
        _maybe_complete(broadcast_id)


@shared_task(bind=True, max_retries=0)
def send_broadcast(self, broadcast_id):
    from broadcast.models import Broadcast
    from notifications.models import Notification

    try:
        broadcast = Broadcast.objects.get(id=broadcast_id)
    except Broadcast.DoesNotExist:
        logger.error(f"Broadcast {broadcast_id} not found")
        return False

    if broadcast.status in ("sending", "sent", "partial") and broadcast.notifications.exists():
        logger.info(f"Broadcast {broadcast_id} already fanned out, skipping duplicate")
        _maybe_complete(broadcast_id)
        return True

    try:
        User = get_user_model()
        users = list(
            User.objects.filter(is_active=True)
            .only("id", "email", "surname", "other_names")
            .iterator(chunk_size=1000)
        )
        broadcast.total = len(users)
        broadcast.sent_count = 0
        broadcast.failed_count = 0
        broadcast.status = "sending"
        broadcast.completed_at = None
        broadcast.save(
            update_fields=["total", "sent_count", "failed_count", "status", "completed_at"]
        )

        Notification.objects.bulk_create(
            [
                Notification(
                    user=u,
                    broadcast=broadcast,
                    title=broadcast.title,
                    message=broadcast.message,
                    notification_type="info",
                    is_read=False,
                )
                for u in users
            ],
            batch_size=500,
        )

        for u in users:
            email_context = {
                "user": {
                    "email": u.email,
                    "first_name": getattr(u, "other_names", ""),
                },
                "title": broadcast.title,
                "message": broadcast.message,
                "notification_type": "info",
            }
            try:
                send_broadcast_email.delay(
                    broadcast_id=broadcast.id,
                    user_email=u.email,
                    email_subject=broadcast.email_subject,
                    email_template=broadcast.template,
                    email_context=email_context,
                )
            except Exception as e:
                # In eager mode the child already counted itself via
                # on_success/on_failure; only count here when merely queueing.
                if settings.CELERY_TASK_ALWAYS_EAGER:
                    logger.warning(
                        f"Broadcast {broadcast_id} email task error for {u.email}: {e}"
                    )
                    continue
                logger.warning(
                    f"Broadcast {broadcast_id} email queue failed for {u.email}: {e}"
                )
                Broadcast.objects.filter(id=broadcast.id).update(
                    failed_count=F("failed_count") + 1
                )
        logger.info(f"Broadcast {broadcast_id} queued for {len(users)} users")
    except Exception as e:
        logger.error(f"Broadcast {broadcast_id} fan-out error: {e}")
        try:
            broadcast.status = "failed"
            broadcast.completed_at = timezone.now()
            broadcast.save(update_fields=["status", "completed_at"])
        except Exception:
            pass
        return False

    _maybe_complete(broadcast_id)
    return True


@shared_task(base=BroadcastEmailTask, bind=True)
def send_broadcast_email(
    self, broadcast_id, user_email, email_subject, email_template, email_context
):
    html_message = render_to_string(email_template, email_context)
    plain_message = strip_tags(html_message)
    send_mail(
        subject=email_subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        html_message=html_message,
        fail_silently=False,
    )
    logger.info(f"Broadcast {broadcast_id} email sent to {user_email}")
    return True
