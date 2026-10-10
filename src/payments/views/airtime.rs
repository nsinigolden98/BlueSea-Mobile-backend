//! Airtime purchases. Mirrors `payments/views.py::AirtimeTopUpViews`.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::validate_airtime;
use crate::payments::views::common;
use crate::state::AppState;
use crate::transactions::nomba_gateway;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/airtime/",
    tag = "Payments",
    summary = "Purchase airtime",
    description = "Purchase airtime for a phone number on a network. Debited from the user wallet on success.",
    request_body = crate::payments::serializers::AirtimeBody,
    responses(
        (status = 200, description = "VTpass response"),
        (status = 400, description = "Validation, PIN or funds failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn airtime(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = match common::pin_gate(&s, headers, &body, true).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let params = match validate_airtime(&body) {
        Ok(p) => p,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };

    let request_id = format!("BS-AIRT{}", crate::payments::vtpass::generate_reference_id());
    let now = crate::time::now_str();
    if let Err(e) = pay_models::insert_airtime(
        &s.db, user.id, params.amount_naira, &params.network, &params.phone, &request_id, &now,
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
    let amount_cents = crate::payments::serializers::naira_to_cents(params.amount_naira);
    // Lock funds BEFORE the gateway call: concurrent requests serialize on
    // the row, so two purchases can't both spend the same balance.
    match wallet_models::lock_amount(&s.db, wallet.id, user.id, amount_cents, crate::accounts::tier::limit_cents(&user)).await {
        Ok(true) => {}
        Ok(false) => return Ok(common::insufficient_funds()),
        Err(e) => return Ok(common::lock_failed(e)),
    }

    let network_upper = params.network.to_uppercase();
    let (ok, data) = nomba_gateway::purchase_airtime(
        &s.config, params.amount_naira, &params.phone, &network_upper, &request_id,
    )
    .await;
    if !ok {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
        let msg = data.as_str().unwrap_or("Airtime purchase failed").to_string();
        return Ok(common::payment_failed(msg));
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
        let desc = common::airtime_desc(&params.network, &params.phone, params.amount_naira);
        if let Err(e) = wallet_models::finalize_locked_debit(
            &s.db, &s.wallet_hub, wallet.id, user.id, amount_cents, &desc, &request_id,
        )
        .await
        {
            // Gateway already delivered: unlock so funds don't stay frozen,
            // then surface loudly (reconciliation needed).
            let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
            tracing::error!("airtime delivered but settle failed for {request_id}: {e:?}");
            return Ok(common::payment_failed(format!("{e:?}")));
        }
        common::settle_success(
            &s, &user, amount_cents, &request_id,
            "Airtime Purchase Successful",
            &format!("₦{} airtime purchased for {}", params.amount_naira, params.phone),
            "BlueSea Mobile - Airtime Purchase",
        )
        .await;
    }
    Ok((StatusCode::OK, Json(resp)))
}
