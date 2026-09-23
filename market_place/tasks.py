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


@shared_task
def send_event_update_notifications(event_id, changes):
    """Mail upcoming ticket holders about a vendor venue/link/time change."""
    from accounts.models import Profile

    from notifications.tasks import send_email_notification
    from notifications.utils import send_notification

    from .models import EventInfo, IssuedTicket

    try:
        event = EventInfo.objects.get(id=event_id)
    except EventInfo.DoesNotExist:
        logger.error(f"Event update task: event {event_id} not found")
        return "Event not found"

    labels = {
        "event_location": "venue",
        "meeting_link": "meeting link",
        "event_date": "date/time",
    }
    lines = [
        f"{labels.get(field, field)} changed"
        for field in (changes or {}).keys()
        if field in labels
    ]
    detail = "; ".join(lines) if lines else "details updated"
    title = f"Event Updated: {event.event_title}"
    message = (
        f"'{event.event_title}' has been updated by the vendor ({detail}). "
        "Your tickets remain valid."
    )
    context = {
        "event_title": event.event_title,
        "changes": changes or {},
        "detail": detail,
    }

    buyer_ids = set(
        IssuedTicket.objects.filter(event=event, status="upcoming")
        .exclude(purchased_by__isnull=True)
        .values_list("purchased_by_id", flat=True)
    )
    sent = 0
    buyer_emails = set()
    for buyer in Profile.objects.filter(id__in=buyer_ids):
        try:
            send_notification(
                user=buyer,
                title=title,
                message=message,
                notification_type="info",
                email_subject=f"BlueSea Mobile - {title}",
                context=context,
            )
            sent += 1
            if buyer.email:
                buyer_emails.add(buyer.email.lower())
        except Exception as e:
            logger.error(f"Event update mail failed for buyer {buyer.id}: {e}")

    owner_emails = set(
        (email or "").strip()
        for email in IssuedTicket.objects.filter(
            event=event, status="upcoming"
        ).values_list("owner_email", flat=True)
    ) - {""}
    for owner_email in sorted(owner_emails):
        if owner_email.lower() in buyer_emails:
            continue
        try:
            owner = Profile.objects.filter(email__iexact=owner_email).first()
            if owner is not None:
                send_notification(
                    user=owner,
                    title=title,
                    message=message,
                    notification_type="info",
                    email_subject=f"BlueSea Mobile - {title}",
                    context=context,
                )
            else:
                send_email_notification.delay(
                    user_email=owner_email,
                    email_subject=f"BlueSea Mobile - {title}",
                    email_template="notifications/default_notification.html",
                    email_context={
                        "user": {"email": owner_email, "first_name": ""},
                        "title": title,
                        "message": message,
                        "notification_type": "info",
                        **context,
                    },
                )
            sent += 1
        except Exception as e:
            logger.error(f"Event update mail failed for {owner_email}: {e}")

    logger.info(f"Event {event_id} update mails sent to {sent} recipient(s)")
    return f"Notified {sent} recipient(s)"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_event_cancellation(self, event_id, reason):
    """Async payout + mail for a vendor-canceled event.

    The vendor wallet was already debited the lump-sum total synchronously
    (reference ``event-cancel-<event_id>``). This task credits each buyer the
    full price paid per ticket and notifies them. Idempotent: skips non-upcoming
    tickets and Wallet.credit dedupes on ``refund-<ticket_id>`` references.
    Tickets whose refund fails stay ``upcoming`` so a replay picks them up.
    """
    from decimal import Decimal

    from django.db import transaction
    from django.db.models import F

    from notifications.tasks import send_email_notification
    from notifications.utils import send_notification
    from wallet.models import Wallet

    from .models import EventInfo, IssuedTicket, TicketType

    try:
        event = EventInfo.objects.get(id=event_id)
    except EventInfo.DoesNotExist:
        logger.error(f"Event cancellation task: event {event_id} not found")
        return "Event not found"

    if not event.is_canceled:
        logger.warning(f"Event cancellation task: event {event_id} not canceled")
        return "Event not canceled; nothing to do"

    cutoff = event.canceled_at or timezone.now()
    ticket_ids = list(
        IssuedTicket.objects.filter(
            event=event, status="upcoming", created_at__lte=cutoff
        )
        .order_by("created_at")
        .values_list("id", flat=True)
    )

    processed = refunded = failed = free = 0
    notify_jobs = []

    for ticket_id in ticket_ids:
        try:
            with transaction.atomic():
                ticket = (
                    IssuedTicket.objects.select_for_update()
                    .select_related("ticket_type", "purchased_by", "event")
                    .get(pk=ticket_id)
                )
                if ticket.status != "upcoming":
                    continue
                now = timezone.now()
                if ticket.ticket_type_id and not ticket.event.is_free:
                    price = ticket.ticket_type.price
                    buyer = ticket.purchased_by
                    if buyer is None:
                        failed += 1
                        continue
                    try:
                        buyer_wallet = Wallet.objects.get(user=buyer)
                    except Wallet.DoesNotExist:
                        logger.error(
                            f"Event cancellation: no wallet for buyer {buyer.id} "
                            f"(ticket {ticket_id})"
                        )
                        failed += 1
                        continue
                    buyer_wallet.credit(
                        amount=price,
                        description=f"Refund: '{ticket.event.event_title}' canceled by vendor",
                        reference=f"refund-{ticket.id}",
                    )
                    ticket.refund_amount = price
                    TicketType.objects.filter(pk=ticket.ticket_type_id).update(
                        quantity_available=F("quantity_available") + 1
                    )
                    try:
                        from affiliate.utils import revoke_sale

                        revoke_sale(ticket)
                    except Exception as aff_exc:
                        logger.error(
                            f"Affiliate revoke failed for ticket {ticket_id}: {aff_exc}"
                        )
                    refunded += 1
                else:
                    ticket.refund_amount = Decimal("0")
                    free += 1
                ticket.status = "canceled"
                ticket.canceled_at = now
                ticket.cancellation_reason = reason
                ticket.save()
                processed += 1
                notify_jobs.append(
                    {
                        "ticket_id": str(ticket.id),
                        "buyer_id": ticket.purchased_by_id,
                        "owner_email": ticket.owner_email,
                        "refund_amount": str(ticket.refund_amount or "0.00"),
                    }
                )
        except IssuedTicket.DoesNotExist:
            continue
        except Exception as e:
            logger.error(
                f"Event cancellation failed for ticket {ticket_id}: {e}",
                exc_info=True,
            )
            failed += 1

    # Best-effort buyer mail (outside ticket locks)
    from accounts.models import Profile

    for job in notify_jobs:
        try:
            from decimal import Decimal

            buyer = Profile.objects.filter(id=job["buyer_id"]).first()
            title = f"Event Canceled: {event.event_title}"
            is_free_ticket = Decimal(job["refund_amount"] or "0") <= 0
            if is_free_ticket:
                message = (
                    f"'{event.event_title}' has been canceled by the vendor. "
                    f"Reason: {reason}"
                )
            else:
                message = (
                    f"'{event.event_title}' has been canceled by the vendor. "
                    f"₦{job['refund_amount']} has been refunded to your wallet. "
                    f"Reason: {reason}"
                )
            context = {
                "event_title": event.event_title,
                "refund_amount": job["refund_amount"],
                "reason": reason,
                "ticket_id": job["ticket_id"],
            }
            if buyer is not None:
                send_notification(
                    user=buyer,
                    title=title,
                    message=message,
                    notification_type="warning",
                    email_subject=f"BlueSea Mobile - {title}",
                    context=context,
                )
            owner_email = (job["owner_email"] or "").strip()
            if owner_email and (
                buyer is None or owner_email.lower() != buyer.email.lower()
            ):
                owner = Profile.objects.filter(email__iexact=owner_email).first()
                if owner is not None:
                    send_notification(
                        user=owner,
                        title=title,
                        message=message,
                        notification_type="warning",
                        email_subject=f"BlueSea Mobile - {title}",
                        context=context,
                    )
                else:
                    send_email_notification.delay(
                        user_email=owner_email,
                        email_subject=f"BlueSea Mobile - {title}",
                        email_template="notifications/default_notification.html",
                        email_context={
                            "user": {"email": owner_email, "first_name": ""},
                            "title": title,
                            "message": message,
                            "notification_type": "warning",
                            **context,
                        },
                    )
        except Exception as e:
            logger.error(
                f"Event cancellation mail failed for ticket {job['ticket_id']}: {e}"
            )

    status = "completed" if failed == 0 else "completed_with_failures"
    EventInfo.objects.filter(id=event.id).update(
        cancel_status=status,
        cancel_processed=processed,
        cancel_refunded=refunded,
        cancel_failed=failed,
    )
    logger.info(
        f"Event {event_id} cancellation {status}: "
        f"{processed} processed ({refunded} refunded, {free} free), {failed} failed"
    )
    return (
        f"{status}: {processed} processed "
        f"({refunded} refunded, {free} free), {failed} failed"
    )