//! Data purchases (MTN/Airtel/Glo/9Mobile).
//! Mirrors `MTNDataTopUpViews`/`AirtelDataTopUpViews`/`GloDataTopUpViews`/
//! `NineMobileDataTopUpViews` — same shape, per-network plans and labels.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::plans::{self, Plan};
use crate::payments::serializers::validate_data_nomba;
use crate::payments::views::common;
use crate::state::AppState;
use crate::transactions::nomba_gateway;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

struct DataKind {
    table: &'static str,
    plans: &'static [Plan],
    /// Nomba network id for vend/fetch (`MTN|AIRTEL|GLO|9MOBILE`).
    network: &'static str,
    /// Plans-cache key (`mtn|airtel|glo|9mobile`).
    cache_key: &'static str,
    network_display: &'static str,
    ref_prefix: &'static str,
    title: &'static str,
    message_network: &'static str,
}

const MTN: DataKind = DataKind {
    table: "payments_mtndatatopup",
    plans: plans::MTN_PLANS,
    network: "MTN",
    cache_key: "mtn",
    network_display: "MTN",
    ref_prefix: "BS-DAT-MTN",
    title: "MTN Data Purchase Successful",
    message_network: "MTN",
};
const AIRTEL: DataKind = DataKind {
    table: "payments_airteldatatopup",
    plans: plans::AIRTEL_PLANS,
    network: "AIRTEL",
    cache_key: "airtel",
    network_display: "Airtel",
    ref_prefix: "BS-DAT-AIR",
    title: "Airtel Data Purchase Successful",
    message_network: "Airtel",
};
const GLO: DataKind = DataKind {
    table: "payments_glodatatopup",
    plans: plans::GLO_PLANS,
    network: "GLO",
    cache_key: "glo",
    network_display: "Glo",
    ref_prefix: "BS-DAT-GLO",
    title: "Glo Data Purchase Successful",
    message_network: "Glo",
};
const NINEMOBILE: DataKind = DataKind {
    table: "payments_etisalatdatatopup",
    plans: plans::NINEMOBILE_PLANS,
    network: "9MOBILE",
    cache_key: "9mobile",
    network_display: "9Mobile",
    ref_prefix: "BS-DAT-ETI",
    title: "9Mobile Data Purchase Successful",
    message_network: "9Mobile",
};

async fn buy_data(
    s: &AppState,
    headers: HeaderMap,
    body: &Value,
    kind: &DataKind,
) -> Resp {
    let user = match common::pin_gate(s, headers, body, true).await {
        Ok(u) => u,
        Err(e) => return e,
    };
    let params = match validate_data_nomba(body) {
        Ok(p) => p,
        Err(e) => return (StatusCode::BAD_REQUEST, Json(e)),
    };
    // Debit amount: plans cache first, legacy static price second, body
    // `amount` third (new Nomba-only clients send plan + amount).
    let amount_naira: i64 = match crate::plans_cache::data_price(&s.plans_store, kind.cache_key, &params.plan) {
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
    if let Err(e) = pay_models::insert_data(
        &s.db, kind.table, user.id, &params.plan, &params.billers_code, &params.phone,
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

    let (ok, data) = nomba_gateway::vend_data(
        &s.config, &params.plan, &params.phone, kind.network, &request_id,
    )
    .await;
    if !ok {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
        let msg = data.as_str().unwrap_or("Data purchase failed").to_string();
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
        let desc = common::data_desc(
            kind.network_display, &params.billers_code, &params.plan, amount_naira,
        );
        if let Err(e) = wallet_models::finalize_locked_debit(
            &s.db, &s.wallet_hub, wallet.id, user.id, amount_cents, &desc, &request_id,
        )
        .await
        {
            let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
            tracing::error!("data delivered but settle failed for {request_id}: {e:?}");
            return common::payment_failed(format!("{e:?}"));
        }
        common::settle_success(
            s, &user, amount_cents, &request_id,
            kind.title,
            &format!("₦{amount_naira} {} data purchased for {}", kind.message_network, params.phone),
            "BlueSea Mobile - Data Purchase",
        )
        .await;
    }
    (StatusCode::OK, Json(resp))
}

#[utoipa::path(
    post, path = "/payments/mtn-data/", tag = "Payments",
    summary = "Purchase MTN data",
    description = "Purchase an MTN data plan. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::DataBody,
    responses((status = 200, description = "VTpass response"), (status = 400, description = "Validation, PIN or funds failure")),
    security(("bearer" = [])),
)]
pub async fn mtn_data(
    State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    Ok(buy_data(&s, headers, &body, &MTN).await)
}

#[utoipa::path(
    post, path = "/payments/airtel-data/", tag = "Payments",
    summary = "Purchase Airtel data",
    description = "Purchase an Airtel data plan. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::DataBody,
    responses((status = 200, description = "VTpass response"), (status = 400, description = "Validation, PIN or funds failure")),
    security(("bearer" = [])),
)]
pub async fn airtel_data(
    State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    Ok(buy_data(&s, headers, &body, &AIRTEL).await)
}

#[utoipa::path(
    post, path = "/payments/glo-data/", tag = "Payments",
    summary = "Purchase Glo data",
    description = "Purchase a Glo data plan. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::DataBody,
    responses((status = 200, description = "VTpass response"), (status = 400, description = "Validation, PIN or funds failure")),
    security(("bearer" = [])),
)]
pub async fn glo_data(
    State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    Ok(buy_data(&s, headers, &body, &GLO).await)
}

#[utoipa::path(
    post, path = "/payments/9mobile-data/", tag = "Payments",
    summary = "Purchase 9Mobile data",
    description = "Purchase a 9mobile data plan. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::DataBody,
    responses((status = 200, description = "VTpass response"), (status = 400, description = "Validation, PIN or funds failure")),
    security(("bearer" = [])),
)]
pub async fn ninemobile_data(
    State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    Ok(buy_data(&s, headers, &body, &NINEMOBILE).await)
}
