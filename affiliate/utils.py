import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import AffiliateProfile, AffiliateLink, AffiliateSale

logger = logging.getLogger(__name__)


def get_affiliate_by_name(name):
    try:
        return AffiliateProfile.objects.get(affiliate_name=name)
    except AffiliateProfile.DoesNotExist:
        return None


def get_active_link(affiliate, event):
    try:
        return AffiliateLink.objects.get(
            affiliate=affiliate, event=event, is_active=True
        )
    except AffiliateLink.DoesNotExist:
        return None


def record_attribution(*, buyer, event, affiliate_name):
    """Record that a buyer used an affiliate link before purchasing.

    First-attribution per (buyer, event) wins. Returns the AffiliateSale
    (status 'pending') or None if the attribution is not valid.
    """
    affiliate = get_affiliate_by_name(affiliate_name)
    if not affiliate or not affiliate.is_approved:
        return None
    if affiliate.user_id == buyer.id:
        return None
    if event.is_free:
        return None
    link = get_active_link(affiliate, event)
    if not link:
        return None

    existing = AffiliateSale.objects.filter(buyer=buyer, event=event).first()
    if existing:
        link.increment_clicks()
        return existing

    sale = AffiliateSale.objects.create(
        affiliate=affiliate,
        link=link,
        event=event,
        buyer=buyer,
        status="pending",
        commission_rate=link.commission_rate,
    )
    link.increment_clicks()
    return sale


def complete_sale(*, buyer, event, affiliate_name, tickets, quantity, total_amount):
    """Finalize a pending attribution, or record a success directly, on purchase.

    Called inside the purchase transaction. Silently returns None when the
    attribution is invalid so the purchase is never blocked by affiliate logic.
    """
    affiliate = get_affiliate_by_name(affiliate_name)
    if not affiliate or not affiliate.is_approved:
        return None
    if affiliate.user_id == buyer.id:
        return None
    if event.is_free or Decimal(str(total_amount)) <= 0:
        return None
    link = get_active_link(affiliate, event)
    if not link:
        return None

    commission = (
        Decimal(str(total_amount)) * link.commission_rate / Decimal("100")
    ).quantize(Decimal("0.01"))
    first_ticket = tickets[0] if tickets else None

    sale = AffiliateSale.objects.filter(buyer=buyer, event=event).first()
    if sale:
        # First-attribution wins: do not override an existing attribution
        if sale.affiliate_id != affiliate.id:
            return None
        if sale.status == "pending":
            sale.status = "success"
            sale.link = link
            sale.issued_ticket = first_ticket
            sale.ticket_count = quantity
            sale.gross_amount = total_amount
            sale.commission_rate = link.commission_rate
            sale.commission_amount = commission
            sale.save()
        return sale

    return AffiliateSale.objects.create(
        affiliate=affiliate,
        link=link,
        event=event,
        buyer=buyer,
        issued_ticket=first_ticket,
        ticket_count=quantity,
        gross_amount=total_amount,
        commission_rate=link.commission_rate,
        commission_amount=commission,
        status="success",
    )


def sweep_payable(affiliate=None):
    """Mark success sales as payable once the event date has passed."""
    now = timezone.now()
    qs = AffiliateSale.objects.filter(status="success", event__event_date__lte=now)
    if affiliate is not None:
        qs = qs.filter(affiliate=affiliate)
    updated = []
    for sale in qs:
        sale.status = "payable"
        sale.payable_at = now
        sale.save(update_fields=["status", "payable_at"])
        updated.append(sale)
    return updated


@transaction.atomic
def pay_out(affiliate):
    """Credit all payable commissions to the affiliate's wallet."""
    sweep_payable(affiliate)
    sales = list(
        AffiliateSale.objects.filter(
            affiliate=affiliate, status="payable"
        ).select_related("affiliate__user")
    )
    if not sales:
        return [], Decimal("0.00")

    wallet = affiliate.user.wallet
    total = Decimal("0.00")
    paid = []
    for sale in sales:
        sale.status = "paid"
        sale.paid_at = timezone.now()
        sale.save(update_fields=["status", "paid_at"])
        total += sale.commission_amount
        paid.append(sale)

    if total > 0:
        wallet.credit(total, description="Affiliate commission payout")
    return paid, total


def revoke_sale(ticket):
    """Revoke a sale whose ticket was canceled/refunded (if not already paid)."""
    if ticket is None:
        return None
    sale = AffiliateSale.objects.filter(
        issued_ticket=ticket, status__in=["success", "payable"]
    ).first()
    if not sale:
        return None
    sale.status = "revoked"
    sale.revoked_at = timezone.now()
    sale.save(update_fields=["status", "revoked_at"])
    return sale
