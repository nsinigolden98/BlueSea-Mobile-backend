import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


def extract_vt_status(response):
    """Map a VTpass /pay response dict to pending/delivered/failed/reversed."""
    if not isinstance(response, dict):
        return "failed"
    inner = {}
    try:
        inner = response.get("content", {}).get("transactions", {}) or {}
    except Exception:
        inner = {}
    if isinstance(inner, dict):
        inner_status = str(inner.get("status") or "").strip().lower()
        if inner_status in ("delivered", "success", "successful", "completed"):
            return "delivered"
        if inner_status in ("reversed", "reversal"):
            return "reversed"
        if inner_status == "failed":
            return "failed"
    rd = str(response.get("response_description", "") or "").lower()
    if "revers" in rd:
        return "reversed"
    if "delivered" in rd or "successful" in rd:
        return "delivered"
    if "fail" in rd:
        return "failed"
    return "pending"


def extract_transaction_id(response):
    """Best-effort VTpass transaction id from a /pay response dict."""
    if not isinstance(response, dict):
        return None
    for key in ("transactionId", "transaction_id", "trans_id", "exchangeReference"):
        val = response.get(key)
        if val:
            return str(val)
    try:
        inner = response.get("content", {}).get("transactions", {}) or {}
    except Exception:
        inner = {}
    if isinstance(inner, dict):
        for key in ("transactionId", "transaction_id", "trans_id"):
            val = inner.get(key)
            if val:
                return str(val)
    return None


def save_vtpass_response(request_id, response):
    """Persist a VTpass /pay response JSON onto its payment record.

    Finds the record across all VTpass-backed payment models by request_id
    (plus GroupPayment by vtu_reference) and stores the raw response dict,
    mapped status, and transaction id. Never raises.
    Returns the updated object, or None when nothing matched.
    """
    from .models import GroupPayment

    if not request_id or not isinstance(response, dict):
        return None
    try:
        from .webhook import PAYMENT_MODELS
    except Exception as e:
        logger.warning(f"save_vtpass_response import failed: {e}")
        return None

    obj = None
    is_group = False
    for model in PAYMENT_MODELS:
        try:
            obj = model.objects.filter(request_id=request_id).first()
            if obj is not None:
                break
        except Exception:
            continue
    if obj is None:
        try:
            obj = GroupPayment.objects.filter(
                Q(vtu_reference=request_id)
                | Q(service_details__request_id=request_id)
            ).first()
            is_group = obj is not None
        except Exception:
            return None
    if obj is None:
        return None

    vt_status = extract_vt_status(response)
    transaction_id = extract_transaction_id(response)
    try:
        obj.vtpass_response = response
        if is_group:
            obj.status = {
                "delivered": "completed",
                "failed": "failed",
                "reversed": "reversed",
            }.get(vt_status, "processing")
        else:
            obj.status = vt_status
            if hasattr(obj, "vtpass_transaction_id") and transaction_id:
                obj.vtpass_transaction_id = transaction_id
        fields = ["vtpass_response", "status"]
        if not is_group and hasattr(obj, "vtpass_transaction_id"):
            fields.append("vtpass_transaction_id")
        if hasattr(obj, "updated_at"):
            fields.append("updated_at")
        obj.save(update_fields=fields)
    except Exception as e:
        logger.warning(f"save_vtpass_response save failed for {request_id}: {e}")
        return None
    return obj
