//! Data purchases (MTN/Airtel/Glo/9Mobile).
//! Mirrors `MTNDataTopUpViews`/`AirtelDataTopUpViews`/`GloDataTopUpViews`/
//! `EtisalatDataTopUpViews` — same shape, per-network plans and labels.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::plans::{self, Plan};
use crate::payments::serializers::validate_data;
use crate::payments::views::common;
use crate::payments::vtpass;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

struct DataKind {
    table: &'static str,
    plans: &'static [Plan],
    service_id: &'static str,
    network_display: &'static str,
    ref_prefix: &'static str,
    title: &'static str,
    message_network: &'static str,
}

const MTN: DataKind = DataKind {
    table: "payments_mtndatatopup",
    plans: plans::MTN_PLANS,
    service_id: "mtn-data",
    network_display: "MTN",
    ref_prefix: "BS-DAT-MTN",
    title: "MTN Data Purchase Successful",
    message_network: "MTN",
};
const AIRTEL: DataKind = DataKind {
    table: "payments_airteldatatopup",
    plans: plans::AIRTEL_PLANS,
    service_id: "airtel-data",
    network_display: "Airtel",
    ref_prefix: "BS-DAT-AIR",
    title: "Airtel Data Purchase Successful",
    message_network: "Airtel",
};
const GLO: DataKind = DataKind {
    table: "payments_glodatatopup",
    plans: plans::GLO_PLANS,
    service_id: "glo-data",
    network_display: "Glo",
    ref_prefix: "BS-DAT-GLO",
    title: "Glo Data Purchase Successful",
    message_network: "Glo",
};
const ETISALAT: DataKind = DataKind {
    table: "payments_etisalatdatatopup",
    plans: plans::ETISALAT_PLANS,
    service_id: "etisalat-data",
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
    let params = match validate_data(body, kind.plans) {
        Ok(p) => p,
        Err(e) => return (StatusCode::BAD_REQUEST, Json(e)),
    };
    let plan = plans::find_plan(kind.plans, &params.plan).expect("validated plan");
    let amount_cents = plan.price_naira * 100;

    let request_id = format!("{}{}", kind.ref_prefix, vtpass::generate_reference_id());
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
    if wallet_models::parse_cents(&wallet.balance).unwrap_or(0) < amount_cents {
        return common::insufficient_funds();
    }

    let payload = serde_json::json!({
        "request_id": request_id,
        "serviceID": kind.service_id,
        "billersCode": params.billers_code,
        "variation_code": plan.code,
        "amount": plan.price_naira,
        "phone": params.phone,
    });
    let resp = match vtpass::top_up(&s.http, &s.config, &payload).await {
        Ok(r) => r,
        Err(e) => return common::payment_failed(e),
    };

    if vtpass::is_successful(&resp) {
        let desc = common::data_desc(
            kind.network_display, &params.billers_code, &params.plan, plan.price_naira,
        );
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
            &format!("₦{} {} data purchased for {}", plan.price_naira, kind.message_network, params.phone),
            "BlueSea - Data Purchase",
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
    post, path = "/payments/etisalat-data/", tag = "Payments",
    summary = "Purchase 9Mobile data",
    description = "Purchase a 9Mobile (Etisalat) data plan. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::DataBody,
    responses((status = 200, description = "VTpass response"), (status = 400, description = "Validation, PIN or funds failure")),
    security(("bearer" = [])),
)]
pub async fn etisalat_data(
    State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    Ok(buy_data(&s, headers, &body, &ETISALAT).await)
}
