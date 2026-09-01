import json
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from transactions.models import WalletTransaction
from wallet.models import Wallet

from .models import (
    VTpassWebhookLog,
    VT_STATUS_CHOICES,
    AirtimeTopUp,
    MTNDataTopUp,
    AirtelDataTopUp,
    GloDataTopUp,
    EtisalatDataTopUp,
    DSTVPayment,
    GOTVPayment,
    StartimesPayment,
    ShowMaxPayment,
    ElectricityPayment,
    WAECRegitration,
    WAECResultChecker,
    JAMBRegistration,
    Airtime2Cash,
    GroupPayment,
)

logger = logging.getLogger(__name__)

PAYMENT_MODELS = (
    AirtimeTopUp,
    MTNDataTopUp,
    AirtelDataTopUp,
    GloDataTopUp,
    EtisalatDataTopUp,
    DSTVPayment,
    GOTVPayment,
    StartimesPayment,
    ShowMaxPayment,
    ElectricityPayment,
    WAECRegitration,
    WAECResultChecker,
    JAMBRegistration,
    Airtime2Cash,
)

VT_STATUS_SET = {c[0] for c in VT_STATUS_CHOICES}


def _find_payment(request_id):
    for model in PAYMENT_MODELS:
        try:
            obj = model.objects.filter(request_id=request_id).first()
            if obj:
                return obj, model.__name__
        except Exception:
            continue
    gp = GroupPayment.objects.filter(
        Q(vtu_reference=request_id) | Q(service_details__request_id=request_id)
    ).first()
    if gp:
        return gp, "GroupPayment"
    return None, None


def _get_amount(data, inner):
    for key in ("amount", "total_amount"):
        val = data.get(key)
        if val is not None:
            try:
                return Decimal(str(val))
            except (InvalidOperation, ValueError, TypeError):
                pass
        val = inner.get(key)
        if val is not None:
            try:
                return Decimal(str(val))
            except (InvalidOperation, ValueError, TypeError):
                pass
    return None


class VTpassWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        if len(request.body) > 1024 * 100:
            logger.warning("VTpass webhook payload too large %s", len(request.body))
            return Response({"response": "success"}, status=status.HTTP_200_OK)
        try:
            try:
                payload = json.loads(
                    request.body.decode("utf-8")
                    if isinstance(request.body, bytes)
                    else request.body
                )
            except Exception:
                payload = request.data if isinstance(request.data, dict) else {}

            if not isinstance(payload, dict):
                logger.warning("VTpass webhook invalid payload type: %s", type(payload))
                return Response({"response": "success"}, status=status.HTTP_200_OK)

            ptype = payload.get("type")
            data = payload.get("data", {})

            if ptype != "transaction-update":
                logger.info("VTpass webhook ignored type=%s payload=%s", ptype, payload)
                return Response({"response": "success"}, status=status.HTTP_200_OK)

            if not isinstance(data, dict):
                logger.warning("VTpass webhook missing data dict: %s", payload)
                return Response({"response": "success"}, status=status.HTTP_200_OK)

            request_id = (
                data.get("requestId")
                or data.get("request_id")
                or payload.get("requestId")
            )
            transaction_id = data.get("transactionId") or data.get("transaction_id")
            code = str(data.get("code", "") or "")

            inner = {}
            try:
                inner = data.get("content", {}).get("transactions", {}) or {}
            except Exception:
                inner = {}

            vt_status = (inner.get("status") or "").strip().lower()
            if not vt_status:
                rd = str(data.get("response_description", "")).lower()
                if "reversal" in rd or "reversed" in rd:
                    vt_status = "reversed"
                elif "delivered" in rd or "successful" in rd:
                    vt_status = "delivered"
                elif "failed" in rd:
                    vt_status = "failed"
                else:
                    vt_status = "pending"

            if vt_status not in VT_STATUS_SET:
                if vt_status in ("success", "successful", "completed"):
                    vt_status = "delivered"
                elif vt_status not in ("pending", "delivered", "failed", "reversed"):
                    logger.info(
                        "VTpass webhook unknown status=%s code=%s", vt_status, code
                    )
                    vt_status = "failed" if code not in ("000", "") else "pending"

            if not transaction_id:
                transaction_id = (
                    inner.get("transactionId")
                    or inner.get("transaction_id")
                    or data.get("wallet_credit_id")
                    or ""
                )

            amount = _get_amount(data, inner)

            log_key = {
                "request_id": request_id or "",
                "transaction_id": transaction_id or "",
                "vt_status": vt_status,
            }

            if not request_id:
                logger.warning("VTpass webhook missing requestId: %s", payload)
                VTpassWebhookLog.objects.create(
                    request_id="",
                    transaction_id=transaction_id or "",
                    vt_status=vt_status,
                    code=code,
                    amount=amount,
                    raw_payload=payload,
                    is_processed=False,
                    error="missing requestId",
                )
                return Response({"response": "success"}, status=status.HTTP_200_OK)

            existing = VTpassWebhookLog.objects.filter(**log_key).first()
            if existing and existing.is_processed:
                return Response({"response": "success"}, status=status.HTTP_200_OK)

            log = existing or VTpassWebhookLog(
                request_id=request_id,
                transaction_id=transaction_id or "",
                vt_status=vt_status,
                code=code,
                amount=amount,
                raw_payload=payload,
            )
            log.code = code
            log.amount = amount
            log.raw_payload = payload

            try:
                with transaction.atomic():
                    obj, model_name = _find_payment(request_id)
                    if obj is None:
                        log.is_processed = False
                        log.error = f"no payment found for request_id={request_id}"
                        log.save()
                        logger.warning(
                            "VTpass webhook no match for request_id=%s", request_id
                        )
                        return Response(
                            {"response": "success"}, status=status.HTTP_200_OK
                        )

                    locked_obj = obj.__class__.objects.select_for_update().get(
                        pk=obj.pk
                    )

                    if hasattr(locked_obj, "status"):
                        if locked_obj.status == vt_status and getattr(
                            locked_obj, "vtpass_transaction_id", None
                        ) == (transaction_id or None):
                            log.is_processed = True
                            log.error = ""
                            log.save()
                            return Response(
                                {"response": "success"}, status=status.HTTP_200_OK
                            )
                        locked_obj.status = vt_status
                        if (
                            hasattr(locked_obj, "vtpass_transaction_id")
                            and transaction_id
                        ):
                            locked_obj.vtpass_transaction_id = transaction_id
                        locked_obj.save(
                            update_fields=[
                                "status",
                                "vtpass_transaction_id",
                                "updated_at",
                            ]
                            if hasattr(locked_obj, "updated_at")
                            else ["status", "vtpass_transaction_id"]
                        )

                    if isinstance(locked_obj, GroupPayment):
                        if vt_status == "delivered":
                            locked_obj.status = "completed"
                        elif vt_status in ("failed", "reversed"):
                            locked_obj.status = vt_status
                        elif vt_status == "pending":
                            locked_obj.status = "processing"
                        locked_obj.save(update_fields=["status", "updated_at"])

                    user = getattr(locked_obj, "user", None) or getattr(
                        locked_obj, "initiated_by", None
                    )

                    if user is not None and vt_status in ("failed", "reversed"):
                        try:
                            wallet = Wallet.objects.select_for_update().get(user=user)
                            debit_exists = WalletTransaction.objects.filter(
                                reference=request_id, transaction_type="DEBIT"
                            ).exists()
                            if debit_exists:
                                reversal_ref = (
                                    f"REV-{request_id}-{transaction_id or 'W'}"[:100]
                                )
                                if not WalletTransaction.objects.filter(
                                    reference=reversal_ref
                                ).exists():
                                    try:
                                        rev_amount = Decimal(
                                            str(getattr(locked_obj, "amount", 0) or 0)
                                        )
                                    except Exception:
                                        rev_amount = Decimal("0")
                                    if rev_amount == Decimal("0") and hasattr(
                                        locked_obj, "total_amount"
                                    ):
                                        try:
                                            rev_amount = Decimal(
                                                str(locked_obj.total_amount)
                                            )
                                        except Exception:
                                            rev_amount = Decimal("0")
                                    if amount is not None and rev_amount != amount:
                                        logger.warning(
                                            "VTpass webhook amount mismatch %s webhook=%s stored=%s",
                                            request_id,
                                            amount,
                                            rev_amount,
                                        )
                                    if rev_amount > 0:
                                        wallet.credit(
                                            amount=rev_amount,
                                            description=f"Refund for {vt_status} transaction {request_id}",
                                            reference=reversal_ref,
                                        )
                                        logger.info(
                                            "VTpass webhook refunded %s to %s for %s",
                                            rev_amount,
                                            user,
                                            request_id,
                                        )
                        except Wallet.DoesNotExist:
                            logger.warning(
                                "VTpass webhook wallet not found for user %s", user
                            )
                        except Exception as e:
                            logger.error(
                                "VTpass webhook refund error %s: %s",
                                request_id,
                                e,
                                exc_info=True,
                            )

                    if isinstance(locked_obj, GroupPayment) and vt_status in (
                        "failed",
                        "reversed",
                    ):
                        try:
                            contributions = locked_obj.contributions.select_related(
                                "member__user"
                            ).all()
                            for contrib in contributions:
                                try:
                                    w = Wallet.objects.select_for_update().get(
                                        user=contrib.member.user
                                    )
                                    rev_ref = f"REV-GP-{locked_obj.id}-{contrib.member.user.id}-{transaction_id or 'W'}"[
                                        :100
                                    ]
                                    if (
                                        not WalletTransaction.objects.filter(
                                            reference=rev_ref
                                        ).exists()
                                        and contrib.status == "completed"
                                    ):
                                        w.credit(
                                            amount=contrib.amount,
                                            description=f"Group payment refund {request_id}",
                                            reference=rev_ref,
                                        )
                                        contrib.status = "reversed"
                                        contrib.save(update_fields=["status"])
                                except Exception as ce:
                                    logger.warning(
                                        "GroupPayment refund failed for contrib %s: %s",
                                        contrib.id,
                                        ce,
                                    )
                        except Exception as e:
                            logger.warning(
                                "GroupPayment webhook handling failed: %s", e
                            )

                    _charge_for_bonus = None
                    if vt_status == "delivered" and user is not None:
                        if isinstance(locked_obj, GroupPayment):
                            try:
                                contributions = locked_obj.contributions.select_related(
                                    "member__user"
                                ).all()
                                for contrib in contributions:
                                    if contrib.status == "completed":
                                        continue
                                    w = Wallet.objects.select_for_update().get(
                                        user=contrib.member.user
                                    )
                                    contrib_ref = f"GP-{locked_obj.id}-{contrib.member.user.id}-{request_id}"[
                                        :100
                                    ]
                                    if not WalletTransaction.objects.filter(
                                        reference=contrib_ref, transaction_type="DEBIT"
                                    ).exists():
                                        if w.balance >= contrib.amount:
                                            w.debit(
                                                amount=contrib.amount,
                                                description=f"Group payment {locked_obj.payment_type} - {request_id}",
                                                reference=contrib_ref,
                                            )
                                            logger.info(
                                                f"GroupPayment debited {contrib.amount} for {contrib.member.user} {request_id}"
                                            )
                                        else:
                                            logger.warning(
                                                f"GroupPayment insufficient funds for {contrib.member.user} {request_id}"
                                            )
                                    contrib.status = "completed"
                                    contrib.save(update_fields=["status"])
                                    if _charge_for_bonus is None:
                                        _charge_for_bonus = contrib.amount
                                    else:
                                        _charge_for_bonus += contrib.amount
                            except Exception as e:
                                logger.warning(
                                    f"GroupPayment delivered handling failed {request_id}: {e}"
                                )
                        else:
                            try:
                                wallet = Wallet.objects.select_for_update().get(
                                    user=user
                                )
                                debit_exists = WalletTransaction.objects.filter(
                                    reference=request_id, transaction_type="DEBIT"
                                ).exists()
                                if not debit_exists:
                                    try:
                                        charge = Decimal(
                                            str(getattr(locked_obj, "amount", 0) or 0)
                                        )
                                    except Exception:
                                        charge = None
                                    if (
                                        charge is None or charge == Decimal("0")
                                    ) and hasattr(locked_obj, "total_amount"):
                                        try:
                                            charge = Decimal(
                                                str(locked_obj.total_amount)
                                            )
                                        except Exception:
                                            charge = None
                                    if (
                                        amount is not None
                                        and charge is not None
                                        and charge != amount
                                    ):
                                        logger.warning(
                                            "VTpass webhook amount mismatch %s webhook=%s stored=%s",
                                            request_id,
                                            amount,
                                            charge,
                                        )
                                        charge = (
                                            Decimal(
                                                str(
                                                    getattr(locked_obj, "amount", 0)
                                                    or 0
                                                )
                                            )
                                            if hasattr(locked_obj, "amount")
                                            else charge
                                        )
                                    if charge is not None and charge > 0:
                                        if wallet.balance >= charge:
                                            wallet.debit(
                                                amount=charge,
                                                description=f"VTpass {locked_obj.__class__.__name__} {request_id}",
                                                reference=request_id,
                                            )
                                            _charge_for_bonus = charge
                                            logger.info(
                                                "VTpass webhook debited %s for delivered %s",
                                                charge,
                                                request_id,
                                            )
                                        else:
                                            _charge_for_bonus = charge
                                else:
                                    try:
                                        _charge_for_bonus = Decimal(
                                            str(getattr(locked_obj, "amount", 0) or 0)
                                        )
                                        if _charge_for_bonus == Decimal(
                                            "0"
                                        ) and hasattr(locked_obj, "total_amount"):
                                            _charge_for_bonus = Decimal(
                                                str(locked_obj.total_amount)
                                            )
                                        if (
                                            amount is not None
                                            and _charge_for_bonus != amount
                                        ):
                                            logger.warning(
                                                "VTpass webhook bonus amount mismatch %s webhook=%s stored=%s",
                                                request_id,
                                                amount,
                                                _charge_for_bonus,
                                            )
                                    except Exception:
                                        _charge_for_bonus = None
                            except Exception as e:
                                logger.warning(
                                    "VTpass webhook delivered debit failed %s: %s",
                                    request_id,
                                    e,
                                )
                        if _charge_for_bonus and _charge_for_bonus > 0:
                            try:
                                from bonus.utils import award_vtu_purchase_points
                                from bonus.models import Referral
                                from bonus.utils import award_referral_bonus

                                award_vtu_purchase_points(
                                    user=user,
                                    purchase_amount=_charge_for_bonus,
                                    reference=request_id,
                                )
                                try:
                                    referral = Referral.objects.get(
                                        referred_user=user,
                                        status="pending",
                                        first_transaction_completed=False,
                                    )
                                    referral.first_transaction_completed = True
                                    referral.save()
                                    award_referral_bonus(referral.referrer, user)
                                except Exception:
                                    pass
                            except Exception as e:
                                logger.warning(
                                    f"VTpass webhook bonus failed {request_id}: {e}"
                                )
                            try:
                                from notifications.utils import send_notification

                                send_notification(
                                    user=user,
                                    title="Transaction Successful",
                                    message=f"Your transaction {request_id} is {vt_status}. Reference: {request_id}",
                                    notification_type="payment_success",
                                    email_subject="BlueSea - Transaction Update",
                                )
                            except Exception as e:
                                logger.warning(
                                    f"VTpass webhook notify failed {request_id}: {e}"
                                )

                    try:
                        from channels.layers import get_channel_layer
                        from asgiref.sync import async_to_sync

                        channel_layer = get_channel_layer()
                        if channel_layer is not None and user is not None:
                            payload_ws = {
                                "type": "payment_update",
                                "reference_id": request_id,
                                "status": vt_status,
                                "payment_type": model_name,
                                "vtpass_transaction_id": transaction_id,
                                "amount": str(amount or _charge_for_bonus or ""),
                            }
                            try:
                                async_to_sync(channel_layer.group_send)(
                                    f"payments_user_{user.id}", payload_ws
                                )
                                async_to_sync(channel_layer.group_send)(
                                    f"payment_{request_id}", payload_ws
                                )
                                if isinstance(locked_obj, GroupPayment):
                                    for (
                                        contrib
                                    ) in locked_obj.contributions.select_related(
                                        "member__user"
                                    ).all():
                                        try:
                                            async_to_sync(channel_layer.group_send)(
                                                f"payments_user_{contrib.member.user.id}",
                                                payload_ws,
                                            )
                                        except Exception:
                                            pass
                            except Exception as e:
                                logger.debug(f"WS push failed {request_id}: {e}")
                    except Exception as e:
                        logger.debug(f"WS channel layer error {request_id}: {e}")

                    log.is_processed = True
                    log.error = ""
                    log.save()
            except Exception as e:
                logger.error(
                    "VTpass webhook processing error for %s: %s",
                    request_id,
                    e,
                    exc_info=True,
                )
                try:
                    log.is_processed = False
                    log.error = str(e)[:1000]
                    log.save()
                except Exception:
                    pass
            return Response({"response": "success"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("VTpass webhook unexpected error: %s", e, exc_info=True)
            return Response({"response": "success"}, status=status.HTTP_200_OK)
