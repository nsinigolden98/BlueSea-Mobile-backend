//! Exam purchases (WAEC registration/result, JAMB).
//! Mirrors the three exam views: fixed prices, `purchased_code`-suffixed
//! descriptions, and — unlike the other VTU views — no outer try/except,
//! with bare `{"error"}` PIN responses.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::{validate_jamb, validate_phone_only};
use crate::payments::views::common;
use crate::payments::vtpass;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

struct ExamKind {
    table: &'static str,
    ref_prefix: &'static str,
    service_id: &'static str,
    variation_code: Option<&'static str>,
    price_naira: Option<i64>,
    jamb_amounts: bool,
    title: &'static str,
    message_kind: &'static str,
    subject: &'static str,
}

const WAEC_REG: ExamKind = ExamKind {
    table: "payments_waecregitration",
    ref_prefix: "BS-WAC-",
    service_id: "waec-registration",
    variation_code: Some("waec-registraion"),
    price_naira: Some(37500),
    jamb_amounts: false,
    title: "WAEC Registration Successful",
    message_kind: "WAEC registration completed for",
    subject: "BlueSea - WAEC Registration",
};
const WAEC_RESULT: ExamKind = ExamKind {
    table: "payments_waecresultchecker",
    ref_prefix: "BS-EPN-",
    service_id: "waec",
    variation_code: Some("waecdirect"),
    price_naira: Some(5350),
    jamb_amounts: false,
    title: "WAEC Result Purchase Successful",
    message_kind: "WAEC result checker PIN purchased for",
    subject: "BlueSea - WAEC Result",
};
const JAMB: ExamKind = ExamKind {
    table: "payments_jambregistration",
    ref_prefix: "BS-JMB-",
    service_id: "jamb",
    variation_code: None,
    price_naira: None,
    jamb_amounts: true,
    title: "JAMB Registration Successful",
    message_kind: "JAMB registration completed for",
    subject: "BlueSea - JAMB Registration",
};

async fn buy_exam(
    s: &AppState,
    headers: HeaderMap,
    body: &Value,
    kind: &ExamKind,
) -> Resp {
    let user = match common::pin_gate(s, headers, body, false).await {
        Ok(u) => u,
        Err(e) => return e,
    };

    // Phone-only for WAEC; billerCode/exam_type/phone for JAMB.
    let (phone, biller_code, exam_type) = if kind.jamb_amounts {
        match validate_jamb(body) {
            Ok(p) => (p.phone, Some(p.biller_code), Some(p.exam_type)),
            Err(e) => return (StatusCode::BAD_REQUEST, Json(e)),
        }
    } else {
        match validate_phone_only(body) {
            Ok(p) => (p, None, None),
            Err(e) => return (StatusCode::BAD_REQUEST, Json(e)),
        }
    };
    let price_naira = match (kind.price_naira, &exam_type) {
        (Some(p), _) => p,
        (None, Some(et)) => {
            if et == "utme-mock" {
                7700
            } else {
                6200
            }
        }
        (None, None) => return common::payment_failed("Unknown exam price"),
    };
    let amount_cents = price_naira * 100;

    let request_id = format!("{}{}", kind.ref_prefix, vtpass::generate_reference_id());
    let now = crate::time::now_str();
    let insert = if kind.jamb_amounts {
        pay_models::insert_jamb(
            &s.db, user.id,
            biller_code.as_deref().unwrap_or(""),
            exam_type.as_deref().unwrap_or(""),
            &phone, &request_id, &now,
        )
        .await
    } else {
        pay_models::insert_exam(&s.db, kind.table, user.id, &phone, &request_id, &now).await
    };
    if let Err(e) = insert {
        return common::payment_failed(e);
    }

    let wallet = match wallet_models::get_by_user(&s.db, user.id).await {
        Ok(Some(w)) => w,
        Ok(None) => return common::payment_failed("Sender wallet not found"),
        Err(e) => return common::payment_failed(e),
    };
    if wallet_models::parse_cents(&wallet.balance).unwrap_or(0) < amount_cents {
        return common::insufficient_funds();
    }

    let mut payload = serde_json::json!({
        "request_id": request_id,
        "serviceID": kind.service_id,
        "quantity": 1,
        "phone": phone,
    });
    if let Some(vc) = kind.variation_code.or(exam_type.as_deref()) {
        payload["variation_code"] = Value::String(vc.to_string());
    }
    if let Some(bc) = biller_code.as_deref() {
        payload["billersCode"] = Value::String(bc.to_string());
    }
    // WAEC payloads carry no billersCode/amount by design.
    let resp = match vtpass::top_up(&s.http, &s.config, &payload).await {
        Ok(r) => r,
        Err(e) => return common::payment_failed(e),
    };

    if vtpass::is_successful(&resp) {
        let purchased = resp.get("purchased_code").and_then(|v| v.as_str());
        let desc = if kind.jamb_amounts {
            common::jamb_desc(exam_type.as_deref().unwrap_or(""), price_naira, purchased)
        } else {
            common::waec_desc(price_naira, purchased)
        };
        if let Err(e) = wallet_models::debit(
            &s.db, &s.wallet_hub, wallet.id, user.id,
            &wallet_models::cents_to_decimal(amount_cents), &desc, Some(&request_id),
        )
        .await
        {
            return common::payment_failed(format!("{e:?}"));
        }
        common::settle_success(
            s, &user, amount_cents, &request_id,
            kind.title,
            &format!("{} {phone}", kind.message_kind),
            kind.subject,
        )
        .await;
    }
    (StatusCode::OK, Json(resp))
}

macro_rules! exam_view {
    ($fn_name:ident, $kind:expr, $path:literal, $summary:literal, $desc:literal, $body:ty) => {
        #[utoipa::path(
            post, path = $path, tag = "Payments",
            summary = $summary, description = $desc,
            request_body = $body,
            responses(
                (status = 200, description = "VTpass response"),
                (status = 400, description = "Validation, PIN or funds failure"),
            ),
            security(("bearer" = [])),
        )]
        pub async fn $fn_name(
            State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
        ) -> Result<Resp, AppError> {
            Ok(buy_exam(&s, headers, &body, $kind).await)
        }
    };
}

exam_view!(
    waec_registration, &WAEC_REG, "/payments/waec-registration/",
    "Purchase WAEC registration", "Purchase WAEC registration (₦37,500 fixed). Debited on success.",
    crate::payments::serializers::PhoneOnlyBody
);
exam_view!(
    waec_result, &WAEC_RESULT, "/payments/waec-result/",
    "Purchase WAEC result checker", "Purchase a WAEC result checker PIN (₦5,350 fixed). Debited on success.",
    crate::payments::serializers::PhoneOnlyBody
);
exam_view!(
    jamb_registration, &JAMB, "/payments/jamb-registration/",
    "Purchase JAMB registration", "Purchase JAMB registration (mock ₦7,700 / no-mock ₦6,200). Debited on success.",
    crate::payments::serializers::JambBody
);
