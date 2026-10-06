//! Airtime purchases. Mirrors `payments/views.py::AirtimeTopUpViews`.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::validate_airtime;
use crate::payments::views::common;
use crate::payments::vtpass;
use crate::state::AppState;
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

    let request_id = format!("BS-AIRT{}", vtpass::generate_reference_id());
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
    let amount_cents = params.amount_naira * 100;
    if wallet_models::parse_cents(&wallet.balance).unwrap_or(0) < amount_cents {
        return Ok(common::insufficient_funds());
    }

    let payload = serde_json::json!({
        "request_id": request_id,
        "serviceID": params.network,
        "amount": params.amount_naira,
        "phone": params.phone,
    });
    let resp = match vtpass::top_up(&s.http, &s.config, &payload).await {
        Ok(r) => r,
        Err(e) => return Ok(common::payment_failed(e)),
    };

    if vtpass::is_successful(&resp) {
        let desc = common::airtime_desc(&params.network, &params.phone, params.amount_naira);
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
            "Airtime Purchase Successful",
            &format!("₦{} airtime purchased for {}", params.amount_naira, params.phone),
            "BlueSea - Airtime Purchase",
        )
        .await;
    }
    Ok((StatusCode::OK, Json(resp)))
}
