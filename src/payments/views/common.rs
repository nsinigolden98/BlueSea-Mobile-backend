//! Shared purchase-flow pieces. Mirrors the repeated blocks in
//! `payments/views.py`: the transaction-PIN gate (two error dialects),
//! `get_payment_description`, and the post-debit bonus + notification tail.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::accounts::pin_security::verify_pin_with_lockout;
use crate::accounts::models::Profile;
use crate::auth::extractor::auth_user;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::state::AppState;

fn pin_err(with_success: bool, message: &str) -> Value {
    if with_success {
        json!({"error": message, "success": false})
    } else {
        json!({"error": message})
    }
}

/// Transaction-PIN gate shared by the purchase views.
/// `with_success` selects the response dialect: VTU views include
/// `"success": false` on 400s, group/internal views do not.
pub async fn pin_gate(
    s: &AppState,
    headers: HeaderMap,
    body: &Value,
    with_success: bool,
) -> Result<Profile, (StatusCode, Json<Value>)> {
    let fail = |status: StatusCode, message: &str| {
        (status, Json(pin_err(with_success, message)))
    };
    let pin = body
        .get("transaction_pin")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if pin.is_empty() {
        return Err(fail(
            StatusCode::BAD_REQUEST,
            "Transaction PIN is required",
        ));
    }
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| fail(StatusCode::UNAUTHORIZED, "Authentication required"))?;
    if !user.pin_is_set {
        return Err(fail(
            StatusCode::BAD_REQUEST,
            "Please set your transaction PIN first",
        ));
    }
    let r = verify_pin_with_lockout(
        &s.db,
        user.id,
        pin,
        &s.config.pin_rsa_private_key_b64,
        s.config.pin_max_attempts as i64,
        s.config.pin_lockout_minutes,
    )
    .await
    .map_err(|_| fail(StatusCode::INTERNAL_SERVER_ERROR, "An error occurred"))?;
    if r.locked {
        let mins = r.retry_after / 60 + 1;
        return Err((
            StatusCode::TOO_MANY_REQUESTS,
            Json(json!({"error": format!("Too many attempts. Try again in {mins} minutes.")})),
        ));
    }
    if !r.ok {
        return Err(fail(StatusCode::BAD_REQUEST, "Invalid transaction PIN"));
    }
    Ok(user)
}

// ---------- descriptions (mirrors get_payment_description) ----------

pub fn last4(phone: &str) -> &str {
    if phone.len() >= 4 {
        &phone[phone.len() - 4..]
    } else {
        phone
    }
}

pub fn airtime_desc(network: &str, phone: &str, amount_naira: i64) -> String {
    format!("AIRTIME: {} {} - ₦{amount_naira}", network.to_uppercase(), last4(phone))
}

pub fn data_desc(network_display: &str, billers_code: &str, plan_display: &str, amount_naira: i64) -> String {
    format!(
        "DATA: {} {} - {plan_display} - ₦{amount_naira}",
        network_display.to_uppercase(),
        last4(billers_code)
    )
}

pub fn cable_desc(kind: &str, phone: &str, plan_display: &str, amount_naira: i64) -> String {
    format!(
        "{kind}: {} - {plan_display} - ₦{amount_naira}",
        last4(phone)
    )
}

fn py_capitalize(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(f) => f.to_uppercase().collect::<String>() + &c.as_str().to_lowercase(),
    }
}

pub fn electricity_desc(biller_name: &str, purchased_code: Option<&str>) -> String {
    let code = purchased_code.unwrap_or(" Debt Paid ");
    format!("Electricity - {} {code}", py_capitalize(biller_name))
}

pub fn waec_desc(amount_naira: i64, purchased_code: Option<&str>) -> String {
    format!(
        "WAEC Registration - ₦{amount_naira} {}",
        purchased_code.unwrap_or("None")
    )
}

pub fn jamb_desc(exam_type: &str, amount_naira: i64, purchased_code: Option<&str>) -> String {
    let kind = if exam_type == "utme-mock" { "UTME Mock" } else { "UTME" };
    format!(
        "JAMB {kind} - ₦{amount_naira} {}",
        purchased_code.unwrap_or("None")
    )
}

// ---------- post-debit tail: bonus hooks + notification ----------

/// Debit-settlement tail shared by purchase views: bonus award stubs,
/// referral first-transaction flag, and the success notification.
/// All failures are swallowed with a log, like Django's nested try/excepts.
pub async fn settle_success(
    s: &AppState,
    user: &Profile,
    amount_cents: i64,
    reference: &str,
    title: &str,
    message: &str,
    email_subject: &str,
) {
    crate::bonus::utils::award_vtu_purchase_points(s, user.id, amount_cents, reference).await;
    match crate::bonus::utils::mark_first_transaction_completed(&s.db, user.id).await {
        Ok(Some(referrer)) => {
            crate::bonus::utils::award_referral_bonus(s, referrer, user.id, &user.email).await
        }
        Ok(None) => {}
        Err(e) => tracing::error!("referral flag error: {e}"),
    }
    let _ = send_notification(
        s,
        user.id,
        &user.email,
        &user.other_names,
        title,
        message,
        "payment_success",
        Some(email_subject),
        NotifyContext::default(),
    )
    .await;
}

/// Insufficient-funds 400 shared by the VTU views
/// (`{"error": "Insufficient Funds", "success": false}`).
pub fn insufficient_funds() -> (StatusCode, Json<Value>) {
    (
        StatusCode::BAD_REQUEST,
        Json(json!({"error": "Insufficient Funds", "success": false})),
    )
}

/// Outer-catch 500 shared by the VTU views
/// (`{"success": false, "error": "Payment failed: ..."}`).
pub fn payment_failed(e: impl std::fmt::Display) -> (StatusCode, Json<Value>) {
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(json!({"success": false, "error": format!("Payment failed: {e}")})),
    )
}

/// Map a wallet-ledger failure to the VTU error dialect.
/// Used for lock/finalize failures on the Nomba rails.
pub fn lock_failed(e: crate::wallet::models::WalletError) -> (StatusCode, Json<Value>) {
    match e {
        crate::wallet::models::WalletError::InsufficientFunds => insufficient_funds(),
        crate::wallet::models::WalletError::Frozen => (
            StatusCode::FORBIDDEN,
            Json(json!({"error": "Account frozen. Contact support.", "success": false})),
        ),
        crate::wallet::models::WalletError::LimitExceeded { limit_cents } => (
            StatusCode::BAD_REQUEST,
            Json(json!({"error": format!(
                "Tier limit exceeded (max {} per account). Upgrade your KYC tier.",
                crate::accounts::tier::limit_naira_display(limit_cents)
            ), "success": false})),
        ),
        crate::wallet::models::WalletError::WalletNotFound => {
            payment_failed("Sender wallet not found")
        }
        other => payment_failed(format!("{other:?}")),
    }
}
