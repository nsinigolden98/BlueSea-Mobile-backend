//! Bank withdrawals. Mirrors `payments/views.py::WithdrawalView` quirk for
//! quirk: serializer validation, PIN gate, DVA routing as an internal
//! transfer, otherwise Paystack recipient + transfer (₦10 fee), debit only
//! after a successful transfer, and the exact success/failure envelopes.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::accounts::models as accounts_models;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::payments::models as pay_models;
use crate::payments::serializers::{WithdrawalPublic, validate_withdrawal};
use crate::payments::vtpass;
use crate::state::AppState;
use crate::transactions::serializers::format_naive_lagos;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/withdrawal/",
    tag = "Withdrawal",
    summary = "Withdrawal via Paystack",
    description = "Withdraw wallet funds to a bank account (minimum ₦500). DVA numbers route as internal transfers.",
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
            // DRF raise_exception → 400 field errors (no envelope).
            return Ok((StatusCode::BAD_REQUEST, Json(e)));
        }
    };
    let pin = body
        .get("transaction_pin")
        .and_then(|v| v.as_str())
        .unwrap_or("");
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

    // DVA routing: account_number matching an active in-system DVA.
    let dva_number = params.account_number.trim().to_string();
    if let Some(dva) = accounts_models::find_dva_by_account_number(&s.db, &dva_number)
        .await
        .unwrap_or(None)
        .filter(|d| d.active)
    {
        return Ok(dva_internal_transfer(&s, &user, &params, &dva, &dva_number).await);
    }

    let wallet = match wallet_models::get_by_user(&s.db, user.id).await {
        Ok(Some(w)) => w,
        _ => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "Insufficient funds", "success": false})),
            ))
        }
    };
    if wallet_models::parse_cents(&wallet.balance).unwrap_or(0) < params.amount_cents {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Insufficient funds", "success": false})),
        ));
    }

    let now = crate::time::now_str();
    let reference_id = format!("BS-WIT-{}", vtpass::generate_reference_id());
    let withdrawal_id = match pay_models::insert_withdrawal(
        &s.db, user.id, &params.account_name, &params.account_number, &params.bank_code,
        &params.bank_name, params.amount_cents, &reference_id, &now,
    )
    .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("Error processing withdrawal: {e}");
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Transfer failed: {e}")})),
            ));
        }
    };

    // Paystack recipient + transfer (synchronous, like Django).
    let recipient = paystack_recipient(
        &s, &params.account_name, &params.account_number, &params.bank_code,
    )
    .await;
    let (recipient_code, fail) = match recipient {
        Ok(code) => (code, None),
        Err(msg) => {
            let _ = pay_models::set_withdrawal_status(
                &s.db, withdrawal_id, "failed", None, None, Some(&crate::time::now_str()),
            )
            .await;
            tracing::error!("Paystack recipient creation failed: {msg}");
            (String::new(), Some(format!("Recipient creation failed: {msg}")))
        }
    };
    if let Some(fail) = fail {
        // Django falls through to the generic 400 Invalid Request envelope.
        let _ = fail;
        return Ok(withdrawal_invalid_request(&s, withdrawal_id).await);
    }
    let _ = pay_models::set_withdrawal_status(
        &s.db, withdrawal_id, "pending", Some(&recipient_code), None, None,
    )
    .await;

    // ₦10 Paystack fee: transfer amount - 1000 kobo.
    let transfer_kobo = params.amount_cents - 1000;
    let transfer = paystack_transfer(
        &s, &recipient_code, transfer_kobo, &reference_id,
        &format!("Transfer to {} ({})", params.account_name, params.account_number),
    )
    .await;
    match transfer {
        Ok(transfer_code) => {
            let completed = crate::time::now_str();
            let _ = pay_models::set_withdrawal_status(
                &s.db, withdrawal_id, "successful", None, Some(&transfer_code), Some(&completed),
            )
            .await;
            let amount_display =
                wallet_models::cents_to_decimal(params.amount_cents);
            if let Err(e) = wallet_models::debit(
                &s.db, &s.wallet_hub, wallet.id, user.id, &amount_display,
                &format!("Transfer  to {} ({})", params.account_name, params.account_number),
                Some(&reference_id),
            )
            .await
            {
                tracing::error!("Paystack auto-transfer error: {e:?}");
                return Ok(withdrawal_invalid_request(&s, withdrawal_id).await);
            }
            let _ = send_notification(
                &s, user.id, &user.email, &user.other_names,
                "Transfer Successful",
                &format!(
                    "₦{amount_display} transfer to {} received. It will be processed shortly.",
                    params.account_name
                ),
                "payment", Some("BlueSea Mobile- Transfer Successful"),
                NotifyContext::default(),
            )
            .await
            .map_err(|e| tracing::error!("Error sending withdrawal notification: {e}"));
            let public = withdrawal_public(&s, withdrawal_id).await;
            Ok((
                StatusCode::OK,
                Json(json!({"state": true, "message": "Transfer successful", "withdrawal": public})),
            ))
        }
        Err(msg) => {
            let completed = crate::time::now_str();
            let _ = pay_models::set_withdrawal_status(
                &s.db, withdrawal_id, "failed", None, None, Some(&completed),
            )
            .await;
            tracing::error!("Paystack transfer initiation failed: {msg}");
            let public = withdrawal_public(&s, withdrawal_id).await;
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({
                    "state": false,
                    "message": "Network Error, Transfer  Failed Try Again Later",
                    "withdrawal": public,
                })),
            ))
        }
    }
}

async fn withdrawal_invalid_request(s: &AppState, withdrawal_id: i64) -> Resp {
    let public = withdrawal_public(s, withdrawal_id).await;
    (
        StatusCode::BAD_REQUEST,
        Json(json!({"state": false, "message": "Invalid Request", "withdrawal": public})),
    )
}

async fn withdrawal_public(s: &AppState, withdrawal_id: i64) -> Value {
        match pay_models::get_withdrawal(&s.db, withdrawal_id).await {
        Ok(Some(w)) => {
            let created = format_naive_lagos(&w.created_at);
            let completed = w.completed_at.as_ref().map(format_naive_lagos);
            let public = WithdrawalPublic::from_row(
                &w,
                &created,
                completed.as_deref(),
            );
            serde_json::to_value(&public).unwrap_or(Value::Null)
        }
        _ => Value::Null,
    }
}

async fn paystack_recipient(
    s: &AppState,
    name: &str,
    account_number: &str,
    bank_code: &str,
) -> Result<String, String> {
    let payload = serde_json::json!({
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "description": format!("Withdrawal to {name} ({account_number})"),
        "currency": "NGN",
    });
    let resp = s
        .http
        .post("https://api.paystack.co/transferrecipient")
        .bearer_auth(&s.config.paystack_secret_key)
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let data: Value = resp.json().await.map_err(|e| e.to_string())?;
    if data.get("status").and_then(|v| v.as_bool()) == Some(true) {
        Ok(data
            .pointer("/data/recipient_code")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string())
    } else {
        Err(data
            .get("message")
            .and_then(|v| v.as_str())
            .unwrap_or("Failed to create recipient")
            .to_string())
    }
}

async fn paystack_transfer(
    s: &AppState,
    recipient_code: &str,
    amount_kobo: i64,
    reference: &str,
    reason: &str,
) -> Result<String, String> {
    let payload = serde_json::json!({
        "source": "balance",
        "amount": amount_kobo,
        "reference": reference,
        "recipient": recipient_code,
        "reason": reason,
        "currency": "NGN",
    });
    let resp = s
        .http
        .post("https://api.paystack.co/transfer")
        .bearer_auth(&s.config.paystack_secret_key)
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let data: Value = resp.json().await.map_err(|e| e.to_string())?;
    if data.get("status").and_then(|v| v.as_bool()) == Some(true) {
        Ok(data
            .pointer("/data/transfer_code")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string())
    } else {
        Err(data
            .get("message")
            .and_then(|v| v.as_str())
            .unwrap_or("Failed to initiate transfer")
            .to_string())
    }
}

async fn dva_internal_transfer(
    s: &AppState,
    user: &crate::accounts::models::Profile,
    params: &crate::payments::serializers::WithdrawalParams,
    dva: &crate::accounts::models::DvaAccount,
    dva_number: &str,
) -> Resp {
    let recipient_id = dva.user_id;
    if recipient_id == user.id {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Cannot transfer to yourself", "success": false})),
        );
    }
    let recipient: Option<(String, String, String)> = sqlx::query_as(
        "SELECT surname, other_names, email FROM accounts_profile WHERE id = ?",
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
            let msg = format!("{e:?}");
            if msg.contains("Insufficient") {
                (
                    StatusCode::BAD_REQUEST,
                    Json(json!({"error": "Insufficient funds", "success": false})),
                )
            } else {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({"success": false, "error": format!("Transfer failed: {msg}")})),
                )
            }
        }
    }
}
