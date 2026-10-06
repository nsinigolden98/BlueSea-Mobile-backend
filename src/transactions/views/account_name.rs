//! Bank account resolution. Mirrors
//! `transactions/views.py::AccountNameView`: Paystack `bank/resolve`,
//! 200 passthrough on success, 404 passthrough on failure, 400 on bad input.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::transactions::paystack;
use crate::transactions::serializers::AccountNameBody;

fn is_digits(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
}

#[utoipa::path(
    post,
    path = "/transactions/account-name/",
    tag = "Wallet & Transactions",
    summary = "Resolve account name",
    description = "Verify a bank account number and retrieve the account holder's name via Paystack",
    request_body = AccountNameBody,
    responses(
        (status = 200, description = "Account resolved"),
        (status = 400, description = "Invalid account number or bank code"),
        (status = 404, description = "Could not resolve account name"),
    ),
    security(("bearer" = [])),
)]
pub async fn account_name(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<AccountNameBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let _user = auth_user(State(s.clone()), headers).await?;
    if !is_digits(&b.account_number) {
        return Err(AppError::bad_request("account_number: A valid integer is required."));
    }
    if !is_digits(&b.bank_code) {
        return Err(AppError::bad_request("bank_code: A valid integer is required."));
    }
    let result: Value = paystack::get_account_name(
        &s.http,
        &s.config.paystack_secret_key,
        &b.account_number,
        &b.bank_code,
    )
    .await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((StatusCode::OK, Json(result)))
    } else {
        Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"success": false, "message": result.get("message")})),
        ))
    }
}
