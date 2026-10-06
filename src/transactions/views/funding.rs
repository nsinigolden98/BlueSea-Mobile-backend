//! Wallet funding init. Mirrors `transactions/views.py::InitializeFunding`:
//! minimum ₦100, PENDING row, Paystack checkout, authorization URL.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::json;
use uuid::Uuid;

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::transactions::models::create_pending_funding;
use crate::transactions::paystack;
use crate::transactions::serializers::InitializeFundingBody;
use crate::wallet::models::{cents_to_decimal, parse_cents};

#[utoipa::path(
    post,
    path = "/transactions/fund-wallet/",
    tag = "Wallet & Transactions",
    summary = "Initialize wallet funding",
    description = "Initialize Paystack payment to fund user wallet (minimum ₦100)",
    request_body = InitializeFundingBody,
    responses(
        (status = 200, description = "Checkout initialized"),
        (status = 400, description = "Below minimum or Paystack failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn initialize_funding(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<InitializeFundingBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;

    let amount_cents = match parse_cents(&b.amount) {
        Ok(c) => c,
        Err(_) => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"success": false, "error": "Invalid amount"})),
            ))
        }
    };
    if amount_cents < 10_000 {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Minimum funding amount is 100.00"})),
        ));
    }

    let payment_reference = format!("BS-DEP-{uuid}", uuid = Uuid::new_v4());
    let now = crate::time::now_str();
    create_pending_funding(&s.db, user.id, amount_cents, &payment_reference, &now).await?;

    let payload = json!({
        "email": user.email,
        "amount": amount_cents,
        "reference": payment_reference,
        "metadata": {"user_id": user.id, "payment_reference": payment_reference},
    });
    let (ok, url_or_error) = paystack::checkout(&s.http, &s.config.paystack_secret_key, &payload).await;
    if !ok {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": url_or_error})),
        ));
    }
    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "authorization_url": url_or_error,
            "payment_reference": payment_reference,
            "amount": cents_to_decimal(amount_cents),
        })),
    ))
}
