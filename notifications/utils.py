from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Notification
import logging

logger = logging.getLogger(__name__)

def send_notification(user, title, message, notification_type='info', email_subject=None, email_template=None, context=None):
    """    
    Args:
        user: User object
        title: Notification title
        message: Notification message
        notification_type: Type of notification (payment, payment_success, contribution, etc.)
        email_subject: Optional custom email subject
        email_template: Optional custom email template name
        context: Additional context for email template
    """
    
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False
    )
    
    try:
        if email_subject is None:
            email_subject = title
        
        if email_template is None:
            email_template = 'notifications/default_notification.html'
        
        email_context = {
            'user': user,
            'title': title,
            'message': message,
            'notification_type': notification_type,
        }
        
        if context:
            email_context.update(context)
        
        html_message = render_to_string(email_template, email_context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=email_subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Email notification sent to {user.email}: {title}")
        
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