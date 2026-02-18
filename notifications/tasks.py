from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_email_notification(self, user_email, email_subject, email_template, email_context):
    """
    Send email notification asynchronously via Celery
    """
    try:
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
        
        logger.info(f"Email notification sent to {user_email}: {email_subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))