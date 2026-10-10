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
use crate::payments::serializers::validate_cable_nomba;
use crate::payments::views::common;
use crate::state::AppState;
use crate::transactions::nomba_gateway;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

struct CableKind {
    table: &'static str,
    plan_col: &'static str,
    plan_field: &'static str,
    plans: &'static [Plan],
    /// Nomba provider id (`DSTV|GOTV|STARTIMES|SHOWMAX`) + cache key.
    provider: &'static str,
    cache_key: &'static str,
    desc_kind: &'static str,
    ref_prefix: &'static str,
    title: &'static str,
    subject: &'static str,
    notify_label: &'static str,
}

const DSTV: CableKind = CableKind {
    table: "payments_dstvpayment", plan_col: "dstv_plan", plan_field: "dstv_plan",
    plans: plans::DSTV_PLANS, provider: "DSTV", cache_key: "dstv", desc_kind: "dstv",
    ref_prefix: "BS-TV-DS",
    title: "DSTV Subscription Successful", subject: "BlueSea Mobile - DSTV Subscription",
    notify_label: "DSTV",
};
const GOTV: CableKind = CableKind {
    table: "payments_gotvpayment", plan_col: "gotv_plan", plan_field: "gotv_plan",
    plans: plans::GOTV_PLANS, provider: "GOTV", cache_key: "gotv", desc_kind: "gotv",
    ref_prefix: "BS-TV-GO",
    title: "GOTV Subscription Successful", subject: "BlueSea Mobile - GOTV Subscription",
    notify_label: "GOTV",
};
const STARTIMES: CableKind = CableKind {
    table: "payments_startimespayment", plan_col: "startimes_plan", plan_field: "startimes_plan",
    plans: plans::STARTIMES_PLANS, provider: "STARTIMES", cache_key: "startimes", desc_kind: "startimes",
    ref_prefix: "BS-TV-STA",
    title: "Startimes Subscription Successful", subject: "BlueSea Mobile - Startimes Subscription",
    notify_label: "Startimes",
};
const SHOWMAX: CableKind = CableKind {
    table: "payments_showmaxpayment", plan_col: "showmax_plan", plan_field: "showmax_plan",
    plans: plans::SHOWMAX_PLANS, provider: "SHOWMAX", cache_key: "showmax", desc_kind: "showmax",
    ref_prefix: "BS-TV-SM",
    title: "ShowMax Subscription Successful", subject: "BlueSea Mobile - ShowMAx Subscription",
    notify_label: "ShowMax",
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
    let params = match validate_cable_nomba(body, kind.plan_field) {
        Ok(p) => p,
        Err(e) => return (StatusCode::BAD_REQUEST, Json(e)),
    };
    let billers_code = params.billers_code.clone();
    // Debit amount: plans cache first, legacy static price second, body
    // `amount` third.
    let amount_naira: i64 = match crate::plans_cache::cable_price(&s.plans_store, kind.cache_key, &params.plan) {
        Some(p) => p,
        None => match plans::find_plan(kind.plans, &params.plan) {
            Some(plan) => plan.price_naira,
            None => match body.get("amount").and_then(|v| match v {
                Value::Number(n) => n.as_i64(),
                Value::String(st) => st.trim().parse::<i64>().ok(),
                _ => None,
            }) {
                Some(a) if (1..=50_000_000).contains(&a) => a,
                Some(_) => {
                    return (
                        StatusCode::BAD_REQUEST,
                        Json(serde_json::json!({"amount": ["Ensure this value is less than or equal to 50000000."]})),
                    )
                }
                None => {
                    return (
                        StatusCode::BAD_REQUEST,
                        Json(serde_json::json!({"amount": ["This field is required."]})),
                    )
                }
            },
        },
    };
    let amount_cents = crate::payments::serializers::naira_to_cents(amount_naira);

    let request_id = format!("{}{}", kind.ref_prefix, crate::payments::vtpass::generate_reference_id());
    let now = crate::time::now_str();
    if let Err(e) = pay_models::insert_cable(
        &s.db, kind.table, kind.plan_col, user.id,
        Some(billers_code.as_str()),
        &params.plan, body.get("subscription_type").and_then(|v| v.as_str()), &params.phone,
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
    // Lock funds BEFORE the gateway call (double-spend guard).
    match wallet_models::lock_amount(&s.db, wallet.id, user.id, amount_cents, crate::accounts::tier::limit_cents(&user)).await {
        Ok(true) => {}
        Ok(false) => return common::insufficient_funds(),
        Err(e) => return common::lock_failed(e),
    }

    let (ok, data) = nomba_gateway::subscribe_cable(
        &s.config, kind.provider, &billers_code, &params.plan, amount_naira,
        &request_id, Some(params.phone.clone()),
    )
    .await;
    if !ok {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
        let msg = data.as_str().unwrap_or("Cable subscription failed").to_string();
        return common::payment_failed(msg);
    }
    let resp = serde_json::json!({
        "success": true,
        "code": "00",
        "description": "TRANSACTION SUCCESSFUL",
        "requestId": request_id,
        "reference": request_id,
        "data": data,
    });

    {
        let desc = common::cable_desc(kind.desc_kind, &billers_code, &params.plan, amount_naira);
        if let Err(e) = wallet_models::finalize_locked_debit(
            &s.db, &s.wallet_hub, wallet.id, user.id, amount_cents, &desc, &request_id,
        )
        .await
        {
            let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
            tracing::error!("cable delivered but settle failed for {request_id}: {e:?}");
            return common::payment_failed(format!("{e:?}"));
        }
        common::settle_success(
            s, &user, amount_cents, &request_id,
            kind.title,
            &format!("{} subscription purchased for {}", kind.notify_label, billers_code),
            kind.subject,
        )
        .await;
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
                (status = 200, description = "Nomba response"),
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
