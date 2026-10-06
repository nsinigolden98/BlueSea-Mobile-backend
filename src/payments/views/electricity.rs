//! Electricity purchases. Mirrors
//! `payments/views.py::ElectricityPaymentViews`: user-supplied amount,
//! disco as VTpass serviceID, phone from the user profile, custom
//! purchased-code description.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::validate_electricity;
use crate::payments::views::common;
use crate::payments::vtpass;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/electricity/",
    tag = "Payments",
    summary = "Purchase electricity units",
    description = "Purchase electricity units for a meter. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::ElectricityBody,
    responses(
        (status = 200, description = "VTpass response"),
        (status = 400, description = "Validation, PIN or funds failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn electricity(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = match common::pin_gate(&s, headers, &body, true).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let params = match validate_electricity(&body) {
        Ok(p) => p,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let amount_cents = params.amount_naira * 100;

    let request_id = format!("BS-LIB{}", vtpass::generate_reference_id());
    let now = crate::time::now_str();
    if let Err(e) = pay_models::insert_electricity(
        &s.db, user.id, &params.biller_code, params.amount_naira, &params.biller_name,
        &params.meter_type, &request_id, &now,
    )
    .await
    {
        return Ok(common::payment_failed(e));
    }

    let wallet = match wallet_models::get_by_user(&s.db, user.id).await {
        Ok(Some(w)) => w,
        Ok(None) => return Ok(common::payment_failed("Sender wallet not found")),
        Err(e) => return Ok(common::payment_failed(e)),
    };
    if wallet_models::parse_cents(&wallet.balance).unwrap_or(0) < amount_cents {
        return Ok(common::insufficient_funds());
    }

    let payload = serde_json::json!({
        "request_id": request_id,
        "serviceID": params.biller_name,
        "billersCode": params.biller_code,
        "variation_code": params.meter_type,
        "amount": params.amount_naira,
        "phone": user.phone.clone().unwrap_or_default(),
    });
    let resp = match vtpass::top_up(&s.http, &s.config, &payload).await {
        Ok(r) => r,
        Err(e) => return Ok(common::payment_failed(e)),
    };

    if vtpass::is_successful(&resp) {
        let purchased = resp.get("purchased_code").and_then(|v| v.as_str());
        let desc = common::electricity_desc(&params.biller_name, purchased);
        if let Err(e) = wallet_models::debit(
            &s.db, &s.wallet_hub, wallet.id, user.id,
            &wallet_models::cents_to_decimal(amount_cents), &desc, Some(&request_id),
        )
        .await
        {
            return Ok(common::payment_failed(format!("{e:?}")));
        }
        common::settle_success(
            &s, &user, amount_cents, &request_id,
            "Electricity Payment Successful",
            &format!("₦{} electricity units purchased for {}", params.amount_naira, params.biller_code),
            "BlueSea Mobile - Electricity Payment",
        )
        .await;
    }
    Ok((StatusCode::OK, Json(resp)))
}
