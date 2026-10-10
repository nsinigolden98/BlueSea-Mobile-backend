//! Customer verification via Nomba: electricity meter, cable smart-card,
//! and betting account lookups. No PIN, no debit; the electricity lookup
//! persists a row like Django did.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::{CustomerVerifyBody, req_str_max};
use crate::state::AppState;
use crate::transactions::nomba_gateway;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/electricity/customer/",
    tag = "Payments",
    summary = "Verify electricity meter",
    description = "Verify a meter number against a disco before purchasing units.",
    request_body = CustomerVerifyBody,
    responses(
        (status = 200, description = "Meter verified"),
        (status = 400, description = "Invalid input or meter not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn verify_customer(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;

    let validated: Result<(String, String, String), Value> = (|| {
        let meter_type = req_str_max(&body, "meter_type", 20)?;
        let meter_number = req_str_max(&body, "meter_number", 15)?;
        let biller = req_str_max(&body, "biller", 60)?;
        Ok((meter_type, meter_number, biller))
    })();
    let (_meter_type, meter_number, biller) = match validated {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let meter_type = _meter_type;

    if let Err(e) = pay_models::insert_customer_lookup(
        &s.db, user.id, &biller, &meter_number, &meter_type,
    )
    .await
    {
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"success": false, "error": format!("Request failed: {e}.")})),
        ));
    }

    let result = nomba_gateway::lookup_electricity_customer(&s.config, &biller, &meter_number).await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((
            StatusCode::OK,
            Json(json!({"success": true, "response": result.get("customer")})),
        ))
    } else {
        let msg = result.get("message").and_then(|v| v.as_str()).unwrap_or("Network Error");
        Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": msg})),
        ))
    }
}

/// Nomba electricity customer lookup (new rail).
/// Body: `{"provider", "meter_number"}`.
pub async fn electricity_lookup(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let provider = match req_str_max(&body, "provider", 60) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let meter = match req_str_max(&body, "meter_number", 20) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let result = nomba_gateway::lookup_electricity_customer(&s.config, &provider, &meter).await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((StatusCode::OK, Json(result)))
    } else {
        Ok((StatusCode::NOT_FOUND, Json(result)))
    }
}

/// Nomba cable smart-card lookup.
/// Body: `{"provider" (dstv|gotv|startimes|showmax), "smart_card_number"}`.
pub async fn cable_lookup(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let provider = match req_str_max(&body, "provider", 60) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let card = match body.get("smart_card_number").and_then(|v| v.as_str()).map(|v| v.trim().to_string()).filter(|v| !v.is_empty()) {
        Some(v) => v,
        None => match req_str_max(&body, "billersCode", 20) {
            Ok(v) => v,
            Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
        },
    };
    let result = nomba_gateway::lookup_cable_customer(&s.config, &provider.to_uppercase(), &card).await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((StatusCode::OK, Json(result)))
    } else {
        Ok((StatusCode::NOT_FOUND, Json(result)))
    }
}

/// Nomba betting account lookup.
/// Body: `{"provider", "customer_id"}`.
pub async fn betting_lookup(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let provider = match req_str_max(&body, "provider", 60) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let customer_id = match req_str_max(&body, "customer_id", 50) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let result = nomba_gateway::lookup_betting_customer(&s.config, &provider, &customer_id).await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((StatusCode::OK, Json(result)))
    } else {
        Ok((StatusCode::NOT_FOUND, Json(result)))
    }
}
