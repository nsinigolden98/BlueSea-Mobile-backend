//! Internal transfers. Mirrors `payments/views.py::InternalTransferView`:
//! email-based wallet-to-wallet moves with paired debit/credit references.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use rust_decimal::Decimal;
use serde_json::{Value, json};

use crate::error::AppError;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::payments::models as pay_models;
use crate::payments::vtpass;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/internal-transfer/",
    tag = "Payments",
    summary = "Transfer funds internally",
    description = "Transfer wallet funds to another BlueSea Mobile user by email.",
    request_body = crate::payments::serializers::InternalTransferBody,
    responses(
        (status = 200, description = "Transfer successful"),
        (status = 400, description = "Validation or funds failure"),
        (status = 404, description = "Recipient not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn internal_transfer(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = match crate::payments::views::common::pin_gate(&s, headers, &body, false).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };

    let recipient_email = body
        .get("email")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if recipient_email.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Recipient email is required"})),
        ));
    }
    let amount: Decimal = match body.get("amount") {
        Some(Value::String(a)) => match a.trim().parse() {
            Ok(d) => d,
            Err(_) => {
                return Ok((
                    StatusCode::BAD_REQUEST,
                    Json(json!({"error": "Valid amount is required"})),
                ))
            }
        },
        Some(Value::Number(n)) => match n.to_string().parse() {
            Ok(d) => d,
            Err(_) => {
                return Ok((
                    StatusCode::BAD_REQUEST,
                    Json(json!({"error": "Valid amount is required"})),
                ))
            }
        },
        _ => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Valid amount is required"})),
            ))
        }
    };
    if amount <= Decimal::ZERO {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Valid amount is required"})),
        ));
    }

    let recipient: Option<(i64, String, String)> = sqlx::query_as(
        "SELECT id, surname, other_names FROM accounts_profile WHERE lower(email) = lower(?)",
    )
    .bind(&recipient_email)
    .fetch_optional(&s.db)
    .await?;
    let Some((recipient_id, surname, other_names)) = recipient else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Recipient not found"})),
        ));
    };
    if recipient_id == user.id {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Cannot transfer to yourself"})),
        ));
    }

    let sender_wallet: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM wallet_wallet WHERE user_id = ?")
            .bind(user.id)
            .fetch_optional(&s.db)
            .await?;
    let Some((sender_wallet_id,)) = sender_wallet else {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Sender wallet not found"})),
        ));
    };
    let recipient_wallet: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM wallet_wallet WHERE user_id = ?")
            .bind(recipient_id)
            .fetch_optional(&s.db)
            .await?;
    let Some((recipient_wallet_id,)) = recipient_wallet else {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Recipient wallet not found"})),
        ));
    };

    let sender_balance: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = ?",
    )
    .bind(sender_wallet_id)
    .fetch_optional(&s.db)
    .await?;
    let sender_dec: rust_decimal::Decimal = sender_balance
        .as_ref()
        .and_then(|(b,)| b.parse().ok())
        .unwrap_or(rust_decimal::Decimal::ZERO);
    if sender_dec < amount {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Insufficient funds"})),
        ));
    }
    // Ledger/debit path is quantized to 2dp like Django's DecimalField.
    let amount_2dp = amount.round_dp_with_strategy(
        2,
        rust_decimal::RoundingStrategy::MidpointNearestEven,
    );
    let amount_display = amount_2dp.to_string();

    let sender_reference = format!("BS-INT-{}", vtpass::generate_reference_id());
    let recipient_reference = format!("BS-INT-{}", vtpass::generate_reference_id());
    let full_name = format!("{surname} {other_names}").trim().to_string();
    let now = crate::time::now_str();
    let transfer_id = match pay_models::insert_internal_transfer(
        &s.db, &sender_reference, user.id,
        (amount_2dp * rust_decimal::Decimal::from(100)).round().to_string().parse::<i64>().unwrap_or(0),
        "", &recipient_email, &full_name, "email", &now,
    )
    .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("Error creating internal transfer record: {e}");
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Transfer failed: {e}")})),
            ));
        }
    };

    match move_funds(
        &s, sender_wallet_id, recipient_wallet_id, user.id, recipient_id,
        &user.email, &recipient_email, &amount_display,
        &sender_reference, &recipient_reference,
    )
    .await
    {
        Ok(()) => {
            let _ = pay_models::set_internal_transfer_status(
                &s.db, transfer_id, "successful", Some(&crate::time::now_str()),
            )
            .await;
            let _ = send_notification(
                &s, user.id, &user.email, &user.other_names,
                "Transfer Successful",
                &format!("₦{amount} transferred to {recipient_email}"),
                "payment_success", Some("BlueSea Mobile - Transfer Successful"),
                NotifyContext::default(),
            )
            .await
            .map_err(|e| tracing::error!("Error sending notification: {e}"));
            let recipient_email_owned = recipient_email.clone();
            let request_email = user.email.clone();
            let _ = send_notification(
                &s, recipient_id, &recipient_email_owned, "",
                "Funds Received",
                &format!("₦{amount} received from {request_email}"),
                "payment_success", Some("BlueSea Mobile - Funds Received"),
                NotifyContext::default(),
            )
            .await
            .map_err(|e| tracing::error!("Error sending notification: {e}"));
            Ok((
                StatusCode::OK,
                Json(json!({
                    "success": true,
                    "message": "Transfer successful",
                    "reference": sender_reference,
                    "amount": amount.to_string(),
                    "recipient": recipient_email,
                    "recipient_name": full_name,
                })),
            ))
        }
        Err(FundsError::Insufficient) => {
            let _ = pay_models::set_internal_transfer_status(
                &s.db, transfer_id, "failed", Some(&crate::time::now_str()),
            )
            .await;
            Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Insufficient funds"})),
            ))
        }
        Err(FundsError::Failed(msg)) => {
            let _ = pay_models::set_internal_transfer_status(
                &s.db, transfer_id, "failed", Some(&crate::time::now_str()),
            )
            .await;
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Transfer failed: {msg}")})),
            ))
        }
    }
}

enum FundsError {
    Insufficient,
    Failed(String),
}

async fn move_funds(
    s: &AppState,
    sender_wallet_id: i64,
    recipient_wallet_id: i64,
    sender_id: i64,
    recipient_id: i64,
    sender_email: &str,
    recipient_email: &str,
    amount_display: &str,
    sender_reference: &str,
    recipient_reference: &str,
) -> Result<(), FundsError> {
    if let Err(e) = wallet_models::debit(
        &s.db, &s.wallet_hub, sender_wallet_id, sender_id, amount_display,
        &format!("Internal transfer to {recipient_email}"), Some(sender_reference),
    )
    .await
    {
        return match e {
            wallet_models::WalletError::InsufficientFunds => Err(FundsError::Insufficient),
            other => Err(FundsError::Failed(format!("{other:?}"))),
        };
    }
    if let Err(e) = wallet_models::credit(
        &s.db, &s.wallet_hub, recipient_wallet_id, recipient_id, amount_display,
        &format!("Internal transfer from {sender_email}"), Some(recipient_reference),
    )
    .await
    {
        return Err(FundsError::Failed(format!("{e:?}")));
    }
    Ok(())
}
