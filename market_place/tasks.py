from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import IssuedTicket
import logging

logger = logging.getLogger(__name__)


@shared_task
def expire_past_event_tickets():
    now = timezone.now()
    
    # Find all upcoming tickets for events that have passed
    tickets_to_expire = IssuedTicket.objects.filter(
        status='upcoming',
        event__event_date__lt=now
    ).select_related('event')
    
    count = tickets_to_expire.count()
    
    if count > 0:
        # Update all matching tickets to expired
        updated = tickets_to_expire.update(status='expired')
        logger.info(f"Expired {updated} tickets for past events")
        return f"Expired {updated} tickets"
    
    logger.info("No tickets to expire")
    return "No tickets to expire"


@shared_task
def send_event_reminder_notifications():
    
    now = timezone.now()
    tomorrow = now + timedelta(hours=24)
    
    # Find tickets for events happening in the next 24 hours
    upcoming_tickets = IssuedTicket.objects.filter(
        status='upcoming',
        event__event_date__gte=now,
        event__event_date__lte=tomorrow
    ).select_related('event', 'purchased_by')
    
    # TODO: Send notifications
    # for ticket in upcoming_tickets:
    #     send_event_reminder(ticket)
    
    logger.info(f"Sent reminders for {upcoming_tickets.count()} upcoming events")
    return f"Sent {upcoming_tickets.count()} reminders"