//! Cable TV purchases (DSTV/GOTV/Startimes/ShowMax).
//! Mirrors the four cable views, including their quirks:
//! - DSTV debits with a `showmax` description and empty plan (copy-paste bug).
//! - ShowMax sends `phone_number` as VTpass `billersCode`, debits with an
//!   empty phone, and never notifies (Django `KeyError` swallowed by logging).

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::plans::{self, Plan};
use crate::payments::serializers::validate_cable;
use crate::payments::views::common;
use crate::payments::vtpass;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

struct CableKind {
    table: &'static str,
    plan_col: &'static str,
    plan_field: &'static str,
    plans: &'static [Plan],
    service_id: &'static str,
    desc_kind: &'static str,
    ref_prefix: &'static str,
    needs_subscription_type: bool,
    title: &'static str,
    subject: &'static str,
    notify_label: &'static str,
    /// None = notify like the others; ShowMax never notifies (Django KeyError).
    notify_smartcard: bool,
}

const DSTV: CableKind = CableKind {
    table: "payments_dstvpayment", plan_col: "dstv_plan", plan_field: "dstv_plan",
    plans: plans::DSTV_PLANS, service_id: "dstv", desc_kind: "showmax",
    ref_prefix: "BS-TV-DS", needs_subscription_type: true,
    title: "DSTV Subscription Successful", subject: "BlueSea Mobile - DSTV Subscription",
    notify_label: "DSTV",
    notify_smartcard: true,
};
const GOTV: CableKind = CableKind {
    table: "payments_gotvpayment", plan_col: "gotv_plan", plan_field: "gotv_plan",
    plans: plans::GOTV_PLANS, service_id: "gotv", desc_kind: "gotv",
    ref_prefix: "BS-TV-GO", needs_subscription_type: true,
    title: "GOTV Subscription Successful", subject: "BlueSea Mobile - GOTV Subscription",
    notify_label: "GOTV",
    notify_smartcard: true,
};
const STARTIMES: CableKind = CableKind {
    table: "payments_startimespayment", plan_col: "startimes_plan", plan_field: "startimes_plan",
    plans: plans::STARTIMES_PLANS, service_id: "startimes", desc_kind: "startimes",
    ref_prefix: "BS-TV-STA", needs_subscription_type: false,
    title: "Startimes Subscription Successful", subject: "BlueSea Mobile - Startimes Subscription",
    notify_label: "Startimes",
    notify_smartcard: true,
};
const SHOWMAX: CableKind = CableKind {
    table: "payments_showmaxpayment", plan_col: "showmax_plan", plan_field: "showmax_plan",
    plans: plans::SHOWMAX_PLANS, service_id: "showmax", desc_kind: "showmax",
    ref_prefix: "BS-TV-SM", needs_subscription_type: false,
    title: "ShowMax Subscription Successful", subject: "BlueSea Mobile - ShowMAx Subscription",
    notify_label: "ShowMax",
    notify_smartcard: false,
};

async fn buy_cable(
    s: &AppState,
    headers: HeaderMap,
    body: &Value,
    kind: &CableKind,
) -> Resp {
    let user = match common::pin_gate(s, headers, body, true).await {
        Ok(u) => u,
        Err(e) => return e,
    };
    let params = match validate_cable(body, kind.plan_field, kind.plans, kind.needs_subscription_type) {
        Ok(p) => p,
        Err(e) => return (StatusCode::BAD_REQUEST, Json(e)),
    };
    // ShowMax posts phone_number as billersCode and has no billersCode field.
    let billers_code = if kind.service_id == "showmax" {
        params.phone.clone()
    } else {
        params.billers_code.clone()
    };
    let plan = plans::find_plan(kind.plans, &params.plan).expect("validated plan");
    let amount_cents = plan.price_naira * 100;

    let request_id = format!("{}{}", kind.ref_prefix, vtpass::generate_reference_id());
    let now = crate::time::now_str();
    if let Err(e) = pay_models::insert_cable(
        &s.db, kind.table, kind.plan_col, user.id,
        if kind.service_id == "showmax" { None } else { Some(billers_code.as_str()) },
        &params.plan, params.subscription_type.as_deref(), &params.phone,
        &request_id, &now,
    )
    .await
    {
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

    let payload = serde_json::json!({
        "request_id": request_id,
        "serviceID": kind.service_id,
        "billersCode": billers_code,
        "variation_code": plan.code,
        "amount": plan.price_naira,
        "phone": params.phone,
    });
    let resp = match vtpass::top_up(&s.http, &s.config, &payload).await {
        Ok(r) => r,
        Err(e) => return common::payment_failed(e),
    };

    if vtpass::is_successful(&resp) {
        // DSTV quirk: description uses kind "showmax" with empty phone/plan.
        let (desc_phone, desc_plan) = if kind.service_id == "dstv" {
            ("", "".to_string())
        } else if kind.service_id == "showmax" {
            // ShowMax quirk: phone lookup misses (no billersCode field).
            ("", params.plan.clone())
        } else {
            (params.billers_code.as_str(), params.plan.clone())
        };
        let desc = common::cable_desc(kind.desc_kind, desc_phone, &desc_plan, plan.price_naira);
        if let Err(e) = wallet_models::debit(
            &s.db, &s.wallet_hub, wallet.id, user.id,
            &wallet_models::cents_to_decimal(amount_cents), &desc, Some(&request_id),
        )
        .await
        {
            return common::payment_failed(format!("{e:?}"));
        }
        if kind.notify_smartcard {
            // ShowMax never notifies: Django's f-string raises KeyError on the
            // missing billersCode inside the notify try-block, which only logs.
            common::settle_success(
                s, &user, amount_cents, &request_id,
                kind.title,
                &format!("{} subscription purchased for {}", kind.notify_label, billers_code),
                kind.subject,
            )
            .await;
        } else {
            // Still run bonus hooks (outside the notify block in Django).
            crate::bonus::utils::award_vtu_purchase_points(s, user.id, amount_cents, &request_id).await;
            match crate::bonus::utils::mark_first_transaction_completed(&s.db, user.id).await {
                Ok(Some(referrer)) => {
                    crate::bonus::utils::award_referral_bonus(s, referrer, user.id, &user.email).await
                }
                Ok(None) => {}
                Err(e) => tracing::error!("referral flag error: {e}"),
            }
        }
    }
    (StatusCode::OK, Json(resp))
}

macro_rules! cable_view {
    ($fn_name:ident, $kind:expr, $path:literal, $summary:literal, $desc:literal) => {
        #[utoipa::path(
            post, path = $path, tag = "Payments",
            summary = $summary, description = $desc,
            request_body = crate::payments::serializers::CableBody,
            responses(
                (status = 200, description = "VTpass response"),
                (status = 400, description = "Validation, PIN or funds failure"),
            ),
            security(("bearer" = [])),
        )]
        pub async fn $fn_name(
            State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
        ) -> Result<Resp, AppError> {
            Ok(buy_cable(&s, headers, &body, $kind).await)
        }
    };
}

cable_view!(
    dstv, &DSTV, "/payments/dstv/", "Purchase DSTV subscription",
    "Purchase a DSTV bouquet. Debited from the user wallet on success."
);
cable_view!(
    gotv, &GOTV, "/payments/gotv/", "Purchase GOTV subscription",
    "Purchase a GOTV bouquet. Debited from the user wallet on success."
);
cable_view!(
    startimes, &STARTIMES, "/payments/startimes/", "Purchase Startimes subscription",
    "Purchase a Startimes bouquet. Debited from the user wallet on success."
);
cable_view!(
    showmax, &SHOWMAX, "/payments/showmax/", "Purchase ShowMax subscription",
    "Purchase a ShowMax plan. Debited from the user wallet on success."
);
