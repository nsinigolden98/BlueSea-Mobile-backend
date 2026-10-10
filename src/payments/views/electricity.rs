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
use crate::state::AppState;
use crate::transactions::nomba_gateway;
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
    let amount_cents = crate::payments::serializers::naira_to_cents(params.amount_naira);

    let request_id = format!("BS-LIB{}", crate::payments::vtpass::generate_reference_id());
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
    // Lock funds BEFORE the gateway call (double-spend guard).
    match wallet_models::lock_amount(&s.db, wallet.id, user.id, amount_cents, crate::accounts::tier::limit_cents(&user)).await {
        Ok(true) => {}
        Ok(false) => return Ok(common::insufficient_funds()),
        Err(e) => return Ok(common::lock_failed(e)),
    }

    let phone = user.phone.clone().unwrap_or_default();
    let (ok, data) = nomba_gateway::vend_electricity(
        &s.config, &params.biller_name, &params.biller_code, params.amount_naira,
        &request_id, Some(phone), Some(params.meter_type.clone()),
    )
    .await;
    if !ok {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
        let msg = data.as_str().unwrap_or("Electricity purchase failed").to_string();
        return Ok(common::payment_failed(msg));
    }
    let token = data.get("token").and_then(|v| v.as_str())
        .or_else(|| data.get("purchased_code").and_then(|v| v.as_str()))
        .or_else(|| data.get("meterToken").and_then(|v| v.as_str()))
        .map(|v| v.to_string());
    let resp = serde_json::json!({
        "success": true,
        "code": "00",
        "description": "TRANSACTION SUCCESSFUL",
        "requestId": request_id,
        "reference": request_id,
        "purchased_code": token,
        "data": data,
    });

    {
        let desc = common::electricity_desc(&params.biller_name, token.as_deref());
        if let Err(e) = wallet_models::finalize_locked_debit(
            &s.db, &s.wallet_hub, wallet.id, user.id, amount_cents, &desc, &request_id,
        )
        .await
        {
            let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
            tracing::error!("electricity delivered but settle failed for {request_id}: {e:?}");
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
