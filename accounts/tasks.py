from celery import shared_task
from .utils import send_email_verification
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_email_task(self, subject, email, template, context):
    
    try:
        result = send_email_verification(
            subject=subject,
            email=email,
            template=template,
            context=context
        )
        return result
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        # Retry after 5 seconds
        raise self.retry(exc=e, countdown=5)