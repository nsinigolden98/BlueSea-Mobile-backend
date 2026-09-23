import logging

from .models import Notification

logger = logging.getLogger(__name__)


def send_notification(user, title, message, notification_type='info', email_subject=None, email_template=None, context=None):    
    """
    Create notification and queue email sending asynchronously
    """
    # Create in-app notification (fast, synchronous)
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False
    )
    
    try:
        from .tasks import send_email_notification
        
        if email_subject is None:
            email_subject = title
        
        if email_template is None:
            email_template = 'notifications/default_notification.html'
        
        email_context = {
            'user': {
                'email': user.email,
                'first_name': user.other_names,
            },
            'title': title,
            'message': message,
            'notification_type': notification_type,
        }
        
        if context:
            email_context.update(context)
        
        send_email_notification.delay(
            user_email=user.email,
            email_subject=email_subject,
            email_template=email_template,
            email_context=email_context
        )
        
        logger.info(f"Email notification queued for {user.email}: {title}")
        
    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {str(e)}")
    
    return notification


def contribution_notification(member, amount, group_name, payment_type):
    title = 'Payment Contribution'
    message = f'₦{amount} debited for {group_name} group payment'
    
    context = {
        'amount': amount,
        'group_name': group_name,
        'payment_type': payment_type,
    }
    
    return send_notification(
        user=member.user,
        title=title,
        message=message,
        notification_type='payment',
        email_subject=f'BlueSea Mobile - {title}',
        email_template='notifications/group_payment_contribution.html',
        context=context
    )


def group_payment_success(member, amount, group_name, payment_type, vtu_reference):
    title = 'Group Purchase Successful'
    message = f'{group_name}: {payment_type} purchase of ₦{amount} completed'
    
    context = {
        'amount': amount,
        'group_name': group_name,
        'payment_type': payment_type,
        'vtu_reference': vtu_reference,
    }
    
    return send_notification(
        user=member.user,
        title=title,
        message=message,
        notification_type='payment_success',
        email_subject=f'BlueSea Mobile - {title}',
        email_template='notifications/group_payment_success.html',
        context=context
    )


def group_payment_failed(member, amount, group_name, payment_type, reason):
    title = 'Group Payment Failed'
    message = f'{group_name}: {payment_type} payment failed. ₦{amount} has been refunded to your wallet'
    
    context = {
        'amount': amount,
        'group_name': group_name,
        'payment_type': payment_type,
        'reason': reason,
    }
    
    return send_notification(
        user=member.user,
        title=title,
        message=message,
        notification_type='payment_failed',
        email_subject=f'BlueSea Mobile - {title}',
        email_template='notifications/group_payment_failed.html',
        context=context
    )


def auto_topup_success():
    pass


def ticket_purchase_notification(buyer, event, tickets, total_cost, reference=None):
    title = 'Ticket Purchase Confirmed'
    quantity = len(tickets)
    if event.is_free:
        message = (
            f'You registered {quantity} free ticket(s) for '
            f"'{event.event_title}'. Your tickets are ready under My Tickets."
        )
    else:
        message = (
            f'You purchased {quantity} ticket(s) for '
            f"'{event.event_title}'. Total paid: ₦{total_cost}."
        )

    rows = []
    for ticket in tickets:
        try:
            ticket_type_name = ticket.ticket_type.name
            price = str(ticket.ticket_type.price)
        except AttributeError:
            ticket_type_name = 'Free Entry'
            price = '0.00'
        rows.append(
            {
                'owner_name': ticket.owner_name,
                'ticket_type': ticket_type_name,
                'price': price,
            }
        )

    context = {
        'event_title': event.event_title,
        'event_date': event.event_date.strftime('%A, %B %d, %Y at %I:%M %p')
        if event.event_date
        else '',
        'event_venue': event.event_location or '',
        'meeting_link': event.meeting_link or '',
        'hosted_by': event.hosted_by or '',
        'tickets': rows,
        'quantity': quantity,
        'total_cost': str(total_cost),
        'reference': reference or '',
    }

    return send_notification(
        user=buyer,
        title=title,
        message=message,
        notification_type='success',
        email_subject=f'BlueSea Mobile - {title}',
        email_template='notifications/ticket_purchase.html',
        context=context
    )