import logging
from celery import shared_task
from requests.exceptions import RequestException
from django.apps import apps

logger = logging.getLogger(__name__)

MODEL_MAP = {
    "AirtimeTopUp": "payments.AirtimeTopUp",
    "MTNDataTopUp": "payments.MTNDataTopUp",
    "AirtelDataTopUp": "payments.AirtelDataTopUp",
    "GloDataTopUp": "payments.GloDataTopUp",
    "EtisalatDataTopUp": "payments.EtisalatDataTopUp",
    "DSTVPayment": "payments.DSTVPayment",
    "GOTVPayment": "payments.GOTVPayment",
    "StartimesPayment": "payments.StartimesPayment",
    "ShowMaxPayment": "payments.ShowMaxPayment",
    "ElectricityPayment": "payments.ElectricityPayment",
    "WAECRegitration": "payments.WAECRegitration",
    "WAECResultChecker": "payments.WAECResultChecker",
    "JAMBRegistration": "payments.JAMBRegistration",
    "GroupPayment": "payments.GroupPayment",
}


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(RequestException,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def call_vtpass_task(self, reference_id, service_data, model_name, object_id):
    try:
        from .vtpass import top_up

        res = top_up(service_data)
        tid = None
        try:
            tid = (
                res.get("transactionId")
                or (res.get("content") or {})
                .get("transactions", {})
                .get("transactionId")
                if isinstance(res.get("content"), dict)
                else None
            )
        except Exception:
            tid = None

        try:
            model_path = MODEL_MAP.get(model_name)
            if model_path:
                Model = apps.get_model(model_path)
                obj = Model.objects.filter(pk=object_id).first()
                if obj and tid and hasattr(obj, "vtpass_transaction_id"):
                    obj.vtpass_transaction_id = tid
                    obj.save(update_fields=["vtpass_transaction_id", "updated_at"])
                    logger.info(
                        f"VTpass async saved {model_name} {reference_id} -> {tid}"
                    )
        except Exception as e:
            logger.warning(f"VTpass task save failed {reference_id}: {e}")

        return {
            "reference_id": reference_id,
            "vtpass_transaction_id": tid,
            "response": res,
        }
    except Exception as e:
        logger.error(f"VTpass task failed {reference_id}: {e}", exc_info=True)
        raise


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(RequestException,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def call_group_vtpass_task(
    self, group_payment_id, payment_type, service_details, total_amount
):
    try:
        from .models import GroupPayment
        from .vtpass import (
            top_up,
            mtn_dict,
            airtel_dict,
            glo_dict,
            etisalat_dict,
            dstv_dict,
            gotv_dict,
            startimes_dict,
            showmax_dict,
            generate_reference_id,
        )

        gp = GroupPayment.objects.filter(pk=group_payment_id).first()
        if not gp:
            logger.warning(f"GroupPayment {group_payment_id} not found for VTpass task")
            return
        request_id = gp.vtu_reference or generate_reference_id()
        gp.vtu_reference = request_id
        if isinstance(gp.service_details, dict):
            gp.service_details["request_id"] = request_id
        gp.save(update_fields=["vtu_reference", "service_details", "updated_at"])

        details = None
        if payment_type == "airtime":
            details = {
                "request_id": request_id,
                "serviceID": service_details.get("network"),
                "amount": int(total_amount),
                "phone": service_details.get("phone_number"),
            }
        elif payment_type == "data":
            net = service_details.get("network")
            plan_id = service_details.get("plan_id")
            if net == "mtn" and plan_id in mtn_dict:
                variation_code, amount = mtn_dict[plan_id]
                details = {
                    "request_id": request_id,
                    "serviceID": "mtn-data",
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get("phone_number"),
                }
            elif net == "airtel" and plan_id in airtel_dict:
                variation_code, amount = airtel_dict[plan_id]
                details = {
                    "request_id": request_id,
                    "serviceID": "airtel-data",
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get("phone_number"),
                }
            elif net == "glo" and plan_id in glo_dict:
                variation_code, amount = glo_dict[plan_id]
                details = {
                    "request_id": request_id,
                    "serviceID": "glo-data",
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get("phone_number"),
                }
            elif net == "etisalat" and plan_id in etisalat_dict:
                variation_code, amount = etisalat_dict[plan_id]
                details = {
                    "request_id": request_id,
                    "serviceID": "etisalat-data",
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get("phone_number"),
                }
        elif payment_type == "electricity":
            details = {
                "request_id": request_id,
                "serviceID": service_details.get("disco"),
                "billersCode": service_details.get("billersCode"),
                "variation_code": service_details.get("meter_type"),
                "amount": int(total_amount),
                "phone": service_details.get("phone_number"),
            }
        elif payment_type in ["dstv", "gotv", "startimes", "showmax"]:
            plan_dict = {
                "dstv": dstv_dict,
                "gotv": gotv_dict,
                "startimes": startimes_dict,
                "showmax": showmax_dict,
            }
            if (
                payment_type in plan_dict
                and service_details.get("plan_id") in plan_dict[payment_type]
            ):
                variation_code, amount = plan_dict[payment_type][
                    service_details.get("plan_id")
                ]
                details = {
                    "request_id": request_id,
                    "serviceID": payment_type,
                    "billersCode": service_details.get("billersCode"),
                    "variation_code": variation_code,
                    "amount": amount,
                    "phone": service_details.get("phone_number"),
                }
        elif payment_type == "jamb":
            details = {
                "request_id": request_id,
                "serviceID": "jamb",
                "variation_code": service_details.get("exam_type"),
                "billersCode": service_details.get("billersCode"),
                "phone": service_details.get("phone_number"),
            }
        elif payment_type == "waec-registration":
            details = {
                "request_id": request_id,
                "serviceID": "waec-registration",
                "variation_code": "waec-registraion",
                "quantity": 1,
                "phone": service_details.get("phone_number"),
            }
        elif payment_type == "waec-result":
            details = {
                "request_id": request_id,
                "serviceID": "waec",
                "variation_code": "waecdirect",
                "quantity": 1,
                "phone": service_details.get("phone_number"),
            }

        if not details:
            logger.warning(
                f"GroupPayment {group_payment_id} unsupported payment_type {payment_type}"
            )
            return

        res = top_up(details)
        tid = (
            res.get("transactionId")
            or (res.get("content") or {}).get("transactions", {}).get("transactionId")
            if isinstance(res.get("content"), dict)
            else None
        )
        if tid:
            gp.refresh_from_db()
            gp.vtpass_transaction_id = (
                tid if hasattr(gp, "vtpass_transaction_id") else tid
            )
            try:
                gp.save(update_fields=["vtpass_transaction_id", "updated_at"])
            except Exception:
                pass
        logger.info(f"Group VTpass async {group_payment_id} -> {tid}")
        return {
            "group_payment_id": group_payment_id,
            "vtpass_transaction_id": tid,
            "response": res,
        }
    except Exception as e:
        logger.error(f"Group VTpass task failed {group_payment_id}: {e}", exc_info=True)
        raise
