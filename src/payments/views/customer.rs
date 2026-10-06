//! Electricity meter verification. Mirrors
//! `payments/views.py::ElectricityPaymentCustomerViews`: no PIN, no debit,
//! persists the lookup, `merchant-verify` gate on `code == "000"`.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::{CustomerVerifyBody, req_str, req_str_max};
use crate::payments::vtpass;
use crate::state::AppState;

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
        let meter_type = req_str(&body, "meter_type")?;
        let meter_number = req_str_max(&body, "meter_number", 15)?;
        let biller = req_str(&body, "biller")?;
        Ok((meter_type, meter_number, biller))
    })();
    let (meter_type, meter_number, biller) = match validated {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };

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

    // int() cast: non-numeric meters raise into the 500 branch, like Django.
    let meter_int: i64 = match meter_number.trim().parse() {
        Ok(n) => n,
        Err(e) => {
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Request failed: {e}.")})),
            ))
        }
    };
    let payload = serde_json::json!({
        "billersCode": meter_int,
        "serviceID": biller,
        "type": meter_type,
    });
    let response = match vtpass::merchant_verify(&s.http, &s.config, &payload).await {
        Ok(r) => r,
        Err(e) => {
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Request failed: {e}.")})),
            ))
        }
    };
    // Missing "code" raises into the 500 branch, like Django's KeyError.
    match response.get("code").and_then(|v| v.as_str()) {
        Some("000") => Ok((
            StatusCode::OK,
            Json(json!({"success": true, "response": response.get("content")})),
        )),
        Some(_) => Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": "Network Error"})),
        )),
        None => Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"success": false, "error": "Request failed: 'code'."})),
        )),
    }
}
