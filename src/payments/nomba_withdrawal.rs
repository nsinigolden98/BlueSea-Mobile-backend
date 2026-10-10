//! Nomba bank withdrawal. Mirrors `payments/nomba_views.py::
//! NombaWithdrawalView`: PIN gate, DVA routing (Nomba table first, then
//! Paystack table) as an internal transfer, otherwise a Nomba bank transfer
//! whose status follows up via the Nomba webhook. Fully async throughout.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::accounts::models as accounts_models;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::payments::models as pay_models;
use crate::payments::serializers::{WithdrawalParams, WithdrawalPublic, validate_withdrawal};
use crate::payments::vtpass;
use crate::state::AppState;
use crate::transactions::nomba_gateway;
use crate::transactions::serializers::format_naive_lagos;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/withdrawal/nomba/",
    tag = "Nomba",
    summary = "Withdrawal via Nomba",
    description = "Withdraw wallet funds to a bank account via Nomba (minimum ₦500). In-system DVA numbers route as internal transfers.",
    request_body = crate::payments::serializers::WithdrawalBody,
    responses(
        (status = 200, description = "Transfer successful or routed internal"),
        (status = 201, description = "Withdrawal submitted"),
        (status = 400, description = "Validation or funds failure"),
        (status = 500, description = "Transfer failed"),
    ),
    security(("bearer" = [])),
)]
pub async fn withdrawal(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let params = match validate_withdrawal(&body) {
        Ok(p) => p,
        Err(e) => {
            return Ok((StatusCode::BAD_REQUEST, Json(e)));
        }
    };
    let pin = body.get("transaction_pin").and_then(|v| v.as_str()).unwrap_or("");
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    if !user.pin_is_set {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Please set your transaction PIN first", "success": false})),
        ));
    }
    let r = crate::accounts::pin_security::verify_pin_with_lockout(
        &s.db, user.id, pin,
        &s.config.pin_rsa_private_key_b64,
        s.config.pin_max_attempts as i64,
        s.config.pin_lockout_minutes,
    )
    .await?;
    if r.locked {
        return Ok((
            StatusCode::TOO_MANY_REQUESTS,
            Json(json!({"error": format!("Too many attempts. Try again in {} minutes.", r.retry_after / 60 + 1)})),
        ));
    }
    if !r.ok {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Invalid transaction PIN", "success": false})),
        ));
    }

    // DVA routing: Nomba table first, then Paystack table (both rails live).
    let dva_number = params.account_number.trim().to_string();
    let mut recipient_id: Option<i64> = None;
    if let Some(dva) = accounts_models::find_active_nomba_dva_by_number(&s.db, &dva_number)
        .await
        .unwrap_or(None)
    {
        recipient_id = Some(dva.user_id);
    } else if let Some(dva) = accounts_models::find_dva_by_account_number(&s.db, &dva_number)
        .await
        .unwrap_or(None)
        .filter(|d| dva_active(d))
    {
        recipient_id = Some(dva.user_id);
    }
    if let Some(recipient_id) = recipient_id {
        return Ok(dva_internal_transfer(&s, &user, &params, recipient_id, &dva_number).await);
    }

    let wallet = match wallet_models::get_by_user(&s.db, user.id).await {
        Ok(Some(w)) => w,
        _ => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Wallet not found", "success": false})),
            ))
        }
    };
    // Lock funds BEFORE the bank transfer: concurrent withdrawals serialize
    // on the row, and money can never leave without the debit locked in.
    match wallet_models::lock_amount(&s.db, wallet.id, user.id, params.amount_cents, crate::accounts::tier::limit_cents(&user)).await {
        Ok(true) => {}
        Ok(false) => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Insufficient funds", "success": false})),
            ))
        }
        Err(e) => {
            return Ok(crate::payments::views::common::lock_failed(e));
        }
    }

    let now = crate::time::now_str();
    let reference_id = format!("BS-WIT-{}", vtpass::generate_reference_id());
    let withdrawal_id = match pay_models::insert_withdrawal(
        &s.db, user.id, &params.account_name, &params.account_number, &params.bank_code,
        &params.bank_name, params.amount_cents, &reference_id, "nomba", &now,
    )
    .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("Error processing Nomba withdrawal: {e}");
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Transfer failed: {e}")})),
            ));
        }
    };

    let sender_name = format!("{} {}", user.surname, user.other_names).trim().to_string();
    let sender_name = if sender_name.is_empty() { user.email.clone() } else { sender_name };
    let (transfer_success, transfer_result) = nomba_gateway::transfer_to_bank(
        &s.config,
        params.amount_cents,
        &params.account_number,
        &params.account_name,
        &params.bank_code,
        &reference_id,
        Some(sender_name),
    )
    .await;
    if !transfer_success {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, params.amount_cents).await;
        let msg = transfer_result.as_str().unwrap_or("Transfer failed").to_string();
        let _ = pay_models::set_withdrawal_status(&s.db, withdrawal_id, "failed", None, None, Some(&now)).await;
        tracing::error!("nomba transfer failed: {msg}");
        // Mirrors Django's inner 400 envelope on gateway failure.
        let public = withdrawal_public(&s, withdrawal_id).await;
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"state": false, "message": "Invalid Request", "withdrawal": public})),
        ));
    }
    let transfer_code = transfer_result
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let _ = pay_models::set_withdrawal_status(
        &s.db, withdrawal_id, "successful", None, Some(&transfer_code), Some(&now),
    )
    .await;
    let amount_display = wallet_models::cents_to_decimal(params.amount_cents);
    // Settle the locked funds after a successful transfer. On DB failure the
    // lock is released and loudly logged (reconciliation needed — the payout
    // webhook will still flip the row on Nomba's confirmation).
    if let Err(e) = wallet_models::finalize_locked_debit(
        &s.db, &s.wallet_hub, wallet.id, user.id, params.amount_cents,
        &format!("Transfer to {} ({}) via Nomba", params.account_name, params.account_number),
        &reference_id,
    )
    .await
    {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, params.amount_cents).await;
        tracing::error!("nomba transferred but settle failed for {reference_id}: {e:?}");
    }
    let _ = send_notification(
        &s, user.id, &user.email, &user.other_names,
        "Transfer Successful",
        &format!("₦{amount_display} transfer to {} received. It will be processed shortly.", params.account_name),
        "payment", Some("BlueSea Mobile- Transfer Successful"),
        NotifyContext::default(),
    )
    .await
    .map_err(|e| tracing::error!("Error sending withdrawal notification: {e}"));
    let public = withdrawal_public(&s, withdrawal_id).await;
    Ok((
        StatusCode::CREATED,
        Json(json!({"state": true, "message": "Transfer successful", "withdrawal": public})),
    ))
}

fn dva_active(d: &accounts_models::DvaAccount) -> bool {
    d.active
}

async fn withdrawal_public(s: &AppState, withdrawal_id: i64) -> Value {
    match pay_models::get_withdrawal(&s.db, withdrawal_id).await.ok().flatten() {
        Some(w) => serde_json::to_value(WithdrawalPublic {
            id: w.id,
            user: w.user_id,
            account_name: w.account_name,
            account_number: w.account_number,
            bank_code: w.bank_code,
            bank_name: w.bank_name,
            amount: crate::wallet::models::dec2(&w.amount),
            status: w.status,
            payment_reference: w.payment_reference,
            recipient_code: w.recipient_code,
            transfer_code: w.transfer_code,
            created_at: format_naive_lagos(&w.created_at),
            completed_at: w.completed_at.as_ref().map(|c| format_naive_lagos(c)),
        })
        .unwrap_or(Value::Null),
        None => Value::Null,
    }
}

async fn dva_internal_transfer(
    s: &AppState,
    user: &crate::accounts::models::Profile,
    params: &WithdrawalParams,
    recipient_id: i64,
    dva_number: &str,
) -> Resp {
    if recipient_id == user.id {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Cannot transfer to yourself", "success": false})),
        );
    }
    let recipient: Option<(String, String, String)> = sqlx::query_as(
        "SELECT surname, other_names, email FROM accounts_profile WHERE id = $1",
    )
    .bind(recipient_id)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    let Some((surname, other_names, recipient_email)) = recipient else {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Recipient wallet not found", "success": false})),
        );
    };
    let sender_wallet = match wallet_models::get_by_user(&s.db, user.id).await {
        Ok(Some(w)) => w,
        _ => {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Sender wallet not found", "success": false})),
            )
        }
    };
    let recipient_wallet = match wallet_models::get_by_user(&s.db, recipient_id).await {
        Ok(Some(w)) => w,
        _ => {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Recipient wallet not found", "success": false})),
            )
        }
    };
    if wallet_models::parse_cents(&sender_wallet.balance).unwrap_or(0) < params.amount_cents {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Insufficient funds", "success": false})),
        );
    }

    let sender_reference = format!("BS-INT-{}", vtpass::generate_reference_id());
    let recipient_reference = format!("BS-INT-{}", vtpass::generate_reference_id());
    let full_name = format!("{surname} {other_names}").trim().to_string();
    let transfer_id = match pay_models::insert_internal_transfer(
        &s.db, &sender_reference, user.id, params.amount_cents, dva_number, &recipient_email,
        &full_name, "dva", &crate::time::now_str(),
    )
    .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("Error creating DVA internal transfer record: {e}");
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Transfer failed: {e}")})),
            );
        }
    };

    let amount_display = wallet_models::cents_to_decimal(params.amount_cents);
    let debit = wallet_models::debit(
        &s.db, &s.wallet_hub, sender_wallet.id, user.id, &amount_display,
        &format!("Internal transfer to {recipient_email} ({dva_number})"),
        Some(&sender_reference),
    )
    .await;
    let credit = match &debit {
        Ok(_) => {
            wallet_models::credit(
                &s.db, &s.wallet_hub, recipient_wallet.id, recipient_id, &amount_display,
                &format!("Internal transfer from {}", user.email),
                Some(&recipient_reference),
            )
            .await
        }
        Err(e) => Err(e.clone()),
    };
    match (debit, credit) {
        (Ok(_), Ok(_)) => {
            let _ = pay_models::set_internal_transfer_status(
                &s.db, transfer_id, "successful", Some(&crate::time::now_str()),
            )
            .await;
            let _ = send_notification(
                s, user.id, &user.email, &user.other_names,
                "Transfer Successful",
                &format!("₦{amount_display} transferred to {recipient_email}"),
                "payment_success", Some("BlueSea Mobile - Transfer Successful"),
                NotifyContext::default(),
            )
            .await
            .map_err(|e| tracing::error!("Error sending notification: {e}"));
            let _ = send_notification(
                s, recipient_id, &recipient_email, &other_names,
                "Funds Received",
                &format!("₦{amount_display} received from {}", user.email),
                "payment_success", Some("BlueSea Mobile - Funds Received"),
                NotifyContext::default(),
            )
            .await
            .map_err(|e| tracing::error!("Error sending notification: {e}"));
            (
                StatusCode::OK,
                Json(json!({
                    "state": true,
                    "message": "Internal tranfer successful",
                    "withdrawal": {
                        "routed_to_internal": true,
                        "transfer_method": "dva",
                        "message": "Transfer successful",
                        "reference": sender_reference,
                        "amount": amount_display,
                        "recipient": recipient_email,
                        "recipient_name": full_name,
                    },
                })),
            )
        }
        (Err(e), _) | (_, Err(e)) => {
            let _ = pay_models::set_internal_transfer_status(
                &s.db, transfer_id, "failed", Some(&crate::time::now_str()),
            )
            .await;
            // Mirrors Django: ValueError -> 400, anything else -> 500.
            match e {
                wallet_models::WalletError::InsufficientFunds => (
                    StatusCode::BAD_REQUEST,
                    Json(json!({"error": "Insufficient funds", "success": false})),
                ),
                wallet_models::WalletError::InvalidAmount => (
                    StatusCode::BAD_REQUEST,
                    Json(json!({"success": false, "error": format!("Transfer failed: {e:?}")})),
                ),
                _ => (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({"success": false, "error": format!("Transfer failed: {e:?}")})),
                ),
            }
        }
    }
}
