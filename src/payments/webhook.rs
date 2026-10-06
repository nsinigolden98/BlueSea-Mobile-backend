//! VTpass `transaction-update` webhook. Mirrors
//! `payments/webhook.py::VTpassWebhookView` (excluded from OpenAPI):
//! always HTTP 200 `{"response": "success"}`, status normalization,
//! idempotent per-payment updates, refunds on failed/reversed, late debits
//! plus bonus hooks on delivered.

use axum::{Json, body::Bytes, extract::State, http::StatusCode};
use rust_decimal::Decimal;
use serde_json::{Value, json};

use crate::auth::extractor::get_profile;
use crate::error::AppError;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::payments::models as pay_models;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

fn ack() -> Resp {
    (StatusCode::OK, Json(json!({"response": "success"})))
}

fn vt_status_set() -> &'static [&'static str] {
    &["pending", "delivered", "failed", "reversed"]
}

/// Normalize the VTpass status exactly like the Django view.
fn normalize_status(inner_status: &str, response_description: &str, code: &str) -> String {
    let mut vt = inner_status.trim().to_lowercase();
    if vt.is_empty() {
        let rd = response_description.to_lowercase();
        if rd.contains("reversal") || rd.contains("reversed") {
            vt = "reversed".to_string();
        } else if rd.contains("delivered") || rd.contains("successful") {
            vt = "delivered".to_string();
        } else if rd.contains("failed") {
            vt = "failed".to_string();
        } else {
            vt = "pending".to_string();
        }
    }
    if !vt_status_set().contains(&vt.as_str()) {
        if ["success", "successful", "completed"].contains(&vt.as_str()) {
            vt = "delivered".to_string();
        } else if !["pending", "delivered", "failed", "reversed"].contains(&vt.as_str()) {
            vt = if code != "000" && !code.is_empty() {
                "failed".to_string()
            } else {
                "pending".to_string()
            };
        }
    }
    vt
}

fn payload_amount(data: &Value, inner: &Value) -> Option<String> {
    for scope in [data, inner] {
        for key in ["amount", "total_amount"] {
            if let Some(v) = scope.get(key) {
                let s = match v {
                    Value::String(s) => s.clone(),
                    Value::Number(n) => n.to_string(),
                    _ => continue,
                };
                if s.parse::<Decimal>().is_ok() {
                    return Some(s);
                }
            }
        }
    }
    None
}

pub async fn vtpass_webhook(
    State(s): State<AppState>,
    body: Bytes,
) -> Result<Resp, AppError> {
    if body.len() > 1024 * 100 {
        tracing::warn!("VTpass webhook payload too large {}", body.len());
        return Ok(ack());
    }
    let payload: Value = match serde_json::from_slice(&body) {
        Ok(Value::Object(_)) => serde_json::from_slice(&body).unwrap_or(Value::Null),
        Ok(_) => return Ok(ack()),
        Err(_) => return Ok(ack()),
    };
    // Non-dict payloads ack, like Django.
    if !payload.is_object() {
        return Ok(ack());
    }
    let ptype = payload.get("type").and_then(|v| v.as_str()).unwrap_or("");
    if ptype != "transaction-update" {
        tracing::info!("VTpass webhook ignored type={ptype}");
        return Ok(ack());
    }
    let data = payload.get("data").cloned().unwrap_or(Value::Null);
    if !data.is_object() {
        return Ok(ack());
    }

    let request_id = data
        .get("requestId")
        .and_then(|v| v.as_str())
        .or_else(|| data.get("request_id").and_then(|v| v.as_str()))
        .or_else(|| payload.get("requestId").and_then(|v| v.as_str()))
        .unwrap_or("")
        .to_string();
    let mut transaction_id = data
        .get("transactionId")
        .and_then(|v| v.as_str())
        .or_else(|| data.get("transaction_id").and_then(|v| v.as_str()))
        .unwrap_or("")
        .to_string();
    let code = data
        .get("code")
        .map(|v| match v {
            Value::String(s) => s.clone(),
            Value::Number(n) => n.to_string(),
            _ => String::new(),
        })
        .unwrap_or_default();

    let inner: Value = data
        .get("content")
        .and_then(|c| c.get("transactions"))
        .cloned()
        .unwrap_or(Value::Null);
    let inner = if inner.is_object() { inner } else { Value::Null };
    let vt_status = normalize_status(
        inner.get("status").and_then(|v| v.as_str()).unwrap_or(""),
        data.get("response_description").and_then(|v| v.as_str()).unwrap_or(""),
        &code,
    );

    if transaction_id.is_empty() {
        transaction_id = inner
            .get("transactionId")
            .and_then(|v| v.as_str())
            .or_else(|| inner.get("transaction_id").and_then(|v| v.as_str()))
            .or_else(|| data.get("wallet_credit_id").and_then(|v| v.as_str()))
            .unwrap_or("")
            .to_string();
    }
    let amount_display = payload_amount(&data, &inner);
    let raw_payload = serde_json::to_string(&payload).unwrap_or_default();
    let now = crate::time::now_str();

    if request_id.is_empty() {
        let _ = pay_models::log_webhook(
            &s.db, "", &transaction_id, &vt_status, &code,
            amount_display.as_deref(), &raw_payload, false, "missing requestId", &now,
        )
        .await;
        return Ok(ack());
    }

    // Idempotency: processed (request_id, transaction_id, vt_status) acks.
    if pay_models::webhook_log_processed(&s.db, &request_id, &transaction_id, &vt_status)
        .await
        .unwrap_or(None)
        == Some(true)
    {
        return Ok(ack());
    }
    let _ = pay_models::log_webhook(
        &s.db, &request_id, &transaction_id, &vt_status, &code,
        amount_display.as_deref(), &raw_payload, false, "", &now,
    )
    .await;

    let outcome = process_update(&s, &request_id, &transaction_id, &vt_status, &code, amount_display.as_deref(), &raw_payload, &now).await;
    if let Err(e) = outcome {
        tracing::error!("VTpass webhook processing error for {request_id}: {e}");
        let _ = pay_models::log_webhook(
            &s.db, &request_id, &transaction_id, &vt_status, &code,
            amount_display.as_deref(), &raw_payload, false, &e[..e.len().min(1000)], &now,
        )
        .await;
    }
    Ok(ack())
}

async fn process_update(
    s: &AppState,
    request_id: &str,
    transaction_id: &str,
    vt_status: &str,
    code: &str,
    amount_display: Option<&str>,
    raw_payload: &str,
    now: &str,
) -> Result<(), String> {
    let found = pay_models::find_by_request_id(&s.db, request_id)
        .await
        .map_err(|e| e.to_string())?;
    let Some(found) = found else {
        pay_models::mark_webhook_processed(
            &s.db, request_id, transaction_id, vt_status, code, amount_display,
            raw_payload, &format!("no payment found for request_id={request_id}"), now,
        )
        .await
        .map_err(|e| e.to_string())?;
        tracing::warn!("VTpass webhook no match for request_id={request_id}");
        return Ok(());
    };

    // Idempotent status write: same status and same VTpass id acks.
    let same_tid = match (
        found.vtpass_transaction_id.as_deref(),
        transaction_id.is_empty(),
    ) {
        (None, true) => true,
        (Some(stored), false) => stored == transaction_id,
        _ => false,
    };
    if found.status == vt_status && same_tid {
        pay_models::mark_webhook_processed(
            &s.db, request_id, transaction_id, vt_status, code, amount_display,
            raw_payload, "", now,
        )
        .await
        .map_err(|e| e.to_string())?;
        return Ok(());
    }
    let table = match found.model_name {
        "AirtimeTopUp" => "payments_airtimetopup",
        "MTNDataTopUp" => "payments_mtndatatopup",
        "AirtelDataTopUp" => "payments_airteldatatopup",
        "GloDataTopUp" => "payments_glodatatopup",
        "EtisalatDataTopUp" => "payments_etisalatdatatopup",
        "DSTVPayment" => "payments_dstvpayment",
        "GOTVPayment" => "payments_gotvpayment",
        "StartimesPayment" => "payments_startimespayment",
        "ShowMaxPayment" => "payments_showmaxpayment",
        "ElectricityPayment" => "payments_electricitypayment",
        "WAECRegitration" => "payments_waecregitration",
        "WAECResultChecker" => "payments_waecresultchecker",
        "JAMBRegistration" => "payments_jambregistration",
        "Airtime2Cash" => "payments_airtime2cash",
        _ => "payments_grouppayment",
    };
    let vt_id = if transaction_id.is_empty() { None } else { Some(transaction_id) };
    if found.model_name == "GroupPayment" {
        let mapped = match vt_status {
            "delivered" => "completed",
            "failed" | "reversed" => vt_status,
            _ => "processing",
        };
        pay_models::set_group_payment_status(&s.db, found.id, mapped, vt_id, now)
            .await
            .map_err(|e| e.to_string())?;
    } else {
        pay_models::update_purchase_status(
            &s.db, table, found.model_name, found.id, vt_status, vt_id, now,
        )
        .await
        .map_err(|e| e.to_string())?;
    }

    let user_id = found.user_id.or(found.initiated_by);
    if found.model_name == "GroupPayment" {
        handle_group_update(s, &found, request_id, vt_status, transaction_id).await;
    } else if let Some(uid) = user_id {
        if vt_status == "failed" || vt_status == "reversed" {
            refund_user(s, uid, &found, request_id, transaction_id, vt_status, amount_display).await;
        } else if vt_status == "delivered" {
            late_debit_user(s, uid, &found, request_id, vt_status, amount_display).await;
        }
    }

    pay_models::mark_webhook_processed(
        &s.db, request_id, transaction_id, vt_status, code, amount_display,
        raw_payload, "", now,
    )
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

async fn wallet_for(s: &AppState, user_id: i64) -> Option<i64> {
    sqlx::query_as::<_, (i64,)>("SELECT id FROM wallet_wallet WHERE user_id = ?")
        .bind(user_id)
        .fetch_optional(&s.db)
        .await
        .unwrap_or(None)
        .map(|(id,)| id)
}

async fn refund_user(
    s: &AppState,
    user_id: i64,
    found: &pay_models::FoundPayment,
    request_id: &str,
    transaction_id: &str,
    vt_status: &str,
    amount_display: Option<&str>,
) {
    let Some(wallet_id) = wallet_for(s, user_id).await else {
        tracing::warn!("VTpass webhook wallet not found for user {user_id}");
        return;
    };
    if !crate::transactions::models::debit_exists(&s.db, request_id)
        .await
        .unwrap_or(false)
    {
        return;
    }
    let reversal_ref = format!(
        "REV-{request_id}-{tid}",
        tid = if transaction_id.is_empty() { "W" } else { transaction_id }
    );
    let reversal_ref: String = reversal_ref.chars().take(100).collect();
    if crate::transactions::models::reference_exists(&s.db, &reversal_ref)
        .await
        .unwrap_or(true)
    {
        return;
    }
    let mut rev = found
        .amount_cents
        .map(|c| wallet_models::cents_to_decimal(c));
    if rev
        .as_deref()
        .map(|r| wallet_models::parse_cents(r).unwrap_or(0))
        .unwrap_or(0)
        == 0
    {
        rev = found
            .total_cents
            .map(|c| wallet_models::cents_to_decimal(c));
    }
    let Some(amount_str) = rev else {
        return;
    };
    if wallet_models::parse_cents(&amount_str).unwrap_or(0) <= 0 {
        return;
    }
    if let (Some(a), Ok(b)) = (
        amount_display,
        amount_str.parse::<Decimal>(),
    ) {
        if a.parse::<Decimal>().ok() != Some(b) {
            tracing::warn!(
                "VTpass webhook amount mismatch {request_id} webhook={a} stored={b}"
            );
        }
    }
    let _ = wallet_models::credit(
        &s.db,
        &s.wallet_hub,
        wallet_id,
        user_id,
        &amount_str,
        &format!("Refund for {vt_status} transaction {request_id}"),
        Some(&reversal_ref),
    )
    .await;
    tracing::info!("VTpass webhook refunded {amount_str} to {user_id} for {request_id}");
}

async fn late_debit_user(
    s: &AppState,
    user_id: i64,
    found: &pay_models::FoundPayment,
    request_id: &str,
    vt_status: &str,
    amount_display: Option<&str>,
) {
    let Some(wallet_id) = wallet_for(s, user_id).await else {
        return;
    };
    // Stored charge (amount column, else group total), like Django's getattr
    // chain. A webhook mismatch only logs — the stored value is charged.
    let mut charge = found
        .amount_cents
        .map(|c| wallet_models::cents_to_decimal(c));
    if charge
        .as_deref()
        .map(|c| wallet_models::parse_cents(c).unwrap_or(0))
        .unwrap_or(0)
        == 0
    {
        charge = found
            .total_cents
            .map(|c| wallet_models::cents_to_decimal(c));
    }
    if let (Some(stored), Some(wh)) = (charge.clone(), amount_display) {
        if stored.parse::<Decimal>().ok() != wh.parse::<Decimal>().ok() {
            tracing::warn!(
                "VTpass webhook amount mismatch {request_id} webhook={wh} stored={stored}"
            );
        }
    }

    if crate::transactions::models::debit_exists(&s.db, request_id)
        .await
        .unwrap_or(false)
    {
        // Already debited synchronously: bonus uses the stored amount.
        deliver_bonus(
            s,
            user_id,
            request_id,
            vt_status,
            charge
                .as_deref()
                .and_then(|c| wallet_models::parse_cents(c).ok())
                .filter(|c| *c > 0),
        )
        .await;
        return;
    }

    let mut bonus_cents = None;
    if let Some(charge_str) = charge {
        if wallet_models::parse_cents(&charge_str).unwrap_or(0) > 0 {
            bonus_cents = wallet_models::parse_cents(&charge_str).ok();
            let balance: Option<(String,)> = sqlx::query_as(
                "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = ?",
            )
            .bind(wallet_id)
            .fetch_optional(&s.db)
            .await
            .unwrap_or(None);
            let funds = balance
                .as_ref()
                .and_then(|(b,)| wallet_models::parse_cents(b).ok())
                .unwrap_or(0);
            if funds >= wallet_models::parse_cents(&charge_str).unwrap_or(i64::MAX) {
                let _ = wallet_models::debit(
                    &s.db, &s.wallet_hub, wallet_id, user_id, &charge_str,
                    &format!("VTpass {} {request_id}", found.model_name),
                    Some(request_id),
                )
                .await;
                tracing::info!("VTpass webhook debited {charge_str} for delivered {request_id}");
            }
        }
    }
    deliver_bonus(s, user_id, request_id, vt_status, bonus_cents).await;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;

    async fn memory_db() -> sqlx::SqlitePool {
        let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        for ddl in [
            "CREATE TABLE accounts_profile (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, password varchar(128) NOT NULL,
             last_login datetime NULL, is_superuser bool NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined datetime NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active bool NOT NULL,
             is_staff bool NOT NULL, is_admin bool NOT NULL, role varchar(200) NOT NULL, email_verified bool NOT NULL,
             created_on datetime NOT NULL, pin_is_set bool NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until datetime NULL, has_DVA bool NOT NULL)",
            "CREATE TABLE wallet_wallet (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, balance decimal NOT NULL,
             locked_balance decimal NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL,
             is_active bool NOT NULL, user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE transactions_wallettransaction (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, amount decimal NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at datetime NOT NULL, wallet_id bigint NOT NULL)",
            "CREATE TABLE notifications_notification (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, title varchar(200) NOT NULL,
             message text NOT NULL, notification_type varchar(20) NOT NULL, is_read bool NOT NULL, created_at datetime NOT NULL,
             read_at datetime NULL, user_id bigint NOT NULL, broadcast_id bigint NULL)",
            "CREATE TABLE payments_airtimetopup (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, amount integer NOT NULL,
             network varchar(10) NOT NULL, phone_number varchar(11) NOT NULL, request_id varchar(50) NULL UNIQUE,
             created_at datetime NOT NULL, user_id bigint NULL, status varchar(20) NOT NULL, updated_at datetime NOT NULL,
             vtpass_transaction_id varchar(100) NULL)",
            "CREATE TABLE payments_vtpasswebhooklog (id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
             request_id varchar(100) NOT NULL, transaction_id varchar(100) NULL, vt_status varchar(20) NULL,
             code varchar(20) NULL, amount decimal NULL, raw_payload text NOT NULL, is_processed bool NOT NULL,
             error text NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL)",
        ] {
            sqlx::query(ddl).execute(&pool).await.unwrap();
        }
        sqlx::query(
            "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
             is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, has_DVA)
             VALUES ('x', 0, '', '', '2026-01-01 00:00:00', 'v@example.com', 'V', 'W', 1, 0, 0, 'user', 1, '2026-01-01 00:00:00', 0, 'ABCDEF', 0, 0)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (10000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1, 1)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO payments_airtimetopup (amount, network, phone_number, request_id, created_at, user_id, status, updated_at)
             VALUES (500, 'mtn', '0801', 'BS-AIRT-1', '2026-01-01 00:00:00', 1, 'pending', '2026-01-01 00:00:00')",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn test_state(db: sqlx::SqlitePool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        config.debug = true;
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
        }
    }

    fn update_payload(request_id: &str, status: &str) -> axum::body::Bytes {
        axum::body::Bytes::from(
            serde_json::json!({
                "type": "transaction-update",
                "data": {
                    "requestId": request_id,
                    "transactionId": "VT-1",
                    "code": "000",
                    "content": {"transactions": {"status": status, "amount": 500}},
                }
            })
            .to_string(),
        )
    }

    #[test]
    fn status_normalization_matches_django() {
        assert_eq!(normalize_status("", "TRANSACTION DELIVERED", ""), "delivered");
        assert_eq!(normalize_status("", "whatever reversal happened", ""), "reversed");
        assert_eq!(normalize_status("", "failed stuff", ""), "failed");
        assert_eq!(normalize_status("", "???", ""), "pending");
        // In-set statuses skip the code fallback, like Django.
        assert_eq!(normalize_status("", "???", "101"), "pending");
        assert_eq!(normalize_status("success", "", ""), "delivered");
        assert_eq!(normalize_status("weird", "", ""), "pending");
        assert_eq!(normalize_status("weird", "", "101"), "failed");
        assert_eq!(normalize_status("Delivered", "", ""), "delivered");
    }

    #[tokio::test]
    async fn delivered_late_debits_and_failed_refunds() {
        let db = memory_db().await;
        let s = test_state(db.clone());

        // delivered with no prior debit -> late debit 500, status delivered
        let resp = vtpass_webhook(State(s.clone()), update_payload("BS-AIRT-1", "delivered"))
            .await
            .unwrap();
        assert_eq!(resp.0, axum::http::StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = 1")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(bal.0, "9500");
        let st: (String,) =
            sqlx::query_as("SELECT status FROM payments_airtimetopup WHERE request_id = 'BS-AIRT-1'")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(st.0, "delivered");

        // duplicate delivered -> ack, no double debit
        let resp = vtpass_webhook(State(s.clone()), update_payload("BS-AIRT-1", "delivered"))
            .await
            .unwrap();
        assert_eq!(resp.0, axum::http::StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = 1")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(bal.0, "9500");

        // failed -> status failed + refund 500 (debit row exists)
        let resp = vtpass_webhook(State(s.clone()), update_payload("BS-AIRT-1", "failed"))
            .await
            .unwrap();
        assert_eq!(resp.0, axum::http::StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = 1")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(bal.0, "10000");

        // oversized body and unknown types ack
        let big = axum::body::Bytes::from(vec![b'x'; 1024 * 100 + 1]);
        let resp = vtpass_webhook(State(s.clone()), big).await.unwrap();
        assert_eq!(resp.0, axum::http::StatusCode::OK);
        let other = axum::body::Bytes::from(r#"{"type":"other"}"#);
        let resp = vtpass_webhook(State(s.clone()), other).await.unwrap();
        assert_eq!(resp.0, axum::http::StatusCode::OK);
    }
}

async fn deliver_bonus(
    s: &AppState,
    user_id: i64,
    request_id: &str,
    vt_status: &str,
    bonus_cents: Option<i64>,
) {
    let Some(cents) = bonus_cents.filter(|c| *c > 0) else {
        return;
    };
    crate::bonus::utils::award_vtu_purchase_points(s, user_id, cents, request_id).await;
    match crate::bonus::utils::mark_first_transaction_completed(&s.db, user_id).await {
        Ok(Some(referrer)) => {
            let email = get_profile(&s.db, user_id)
                .await
                .map(|u| u.email)
                .unwrap_or_default();
            crate::bonus::utils::award_referral_bonus(s, referrer, user_id, &email).await
        }
        Ok(None) => {}
        Err(e) => tracing::warn!("VTpass webhook bonus failed {request_id}: {e}"),
    }
    if let Ok(user) = get_profile(&s.db, user_id).await {
        let _ = send_notification(
            s, user.id, &user.email, &user.other_names,
            "Transaction Successful",
            &format!("Your transaction {request_id} is {vt_status}. Reference: {request_id}"),
            "payment_success", Some("BlueSea Mobile - Transaction Update"),
            NotifyContext::default(),
        )
        .await
        .map_err(|e| tracing::warn!("VTpass webhook notify failed {request_id}: {e}"));
    }
}

// ---------- group payment webhook branches ----------

async fn handle_group_update(
    s: &AppState,
    found: &pay_models::FoundPayment,
    request_id: &str,
    vt_status: &str,
    transaction_id: &str,
) {
    let contribs = match pay_models::contributions_with_users(&s.db, found.id).await {
        Ok(c) => c,
        Err(e) => {
            tracing::warn!("GroupPayment webhook handling failed: {e}");
            return;
        }
    };
    if vt_status == "failed" || vt_status == "reversed" {
        for (c, uid, _name, _email) in &contribs {
            if let Some(wallet_id) = wallet_for(s, *uid).await {
                let rev_ref = format!(
                    "REV-GP-{}-{uid}-{tid}",
                    found.id,
                    tid = if transaction_id.is_empty() { "W" } else { transaction_id }
                );
                let rev_ref: String = rev_ref.chars().take(100).collect();
                let already = crate::transactions::models::reference_exists(&s.db, &rev_ref)
                    .await
                    .unwrap_or(true);
                let completed = c.status == "completed";
                if !already && completed {
                    if let Ok(amount_dec) = c.amount.parse::<Decimal>() {
                        if amount_dec > Decimal::ZERO {
                            let _ = wallet_models::credit_decimal(
                                &s.db, &s.wallet_hub, wallet_id, *uid, amount_dec,
                                &format!("Group payment refund {}", c.id),
                                &rev_ref,
                            )
                            .await
                            .map_err(|e| tracing::warn!("GroupPayment refund failed for contrib {}: {e:?}", c.id));
                            let _ = pay_models::set_contributions_status(
                                &s.db, found.id, Some(c.member_id), "reversed",
                            )
                            .await;
                        }
                    }
                }
            }
        }
        return;
    }
    if vt_status != "delivered" {
        return;
    }
    let mut bonus_sum = Decimal::ZERO;
    let mut any_bonus = false;
    for (c, uid, _name, _email) in &contribs {
        if c.status == "completed" {
            continue;
        }
        let Some(wallet_id) = wallet_for(s, *uid).await else {
            continue;
        };
        let contrib_ref = format!("GP-{}-{uid}-{request_id}", found.id);
        let contrib_ref: String = contrib_ref.chars().take(100).collect();
        let amount_dec = c.amount.parse::<Decimal>().unwrap_or(Decimal::ZERO);
        if !crate::transactions::models::debit_exists(&s.db, &contrib_ref)
            .await
            .unwrap_or(false)
        {
            let balance: Option<(String,)> = sqlx::query_as(
                "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = ?",
            )
            .bind(wallet_id)
            .fetch_optional(&s.db)
            .await
            .unwrap_or(None);
            let funds = balance
                .as_ref()
                .and_then(|(b,)| b.parse::<Decimal>().ok())
                .unwrap_or(Decimal::ZERO);
            if funds >= amount_dec {
                let _ = wallet_models::debit_decimal(
                    &s.db, &s.wallet_hub, wallet_id, *uid, amount_dec,
                    &format!("Group payment {} - {contrib_ref}", found.id),
                    &contrib_ref,
                )
                .await
                .map_err(|e| {
                    tracing::warn!("GroupPayment insufficient funds for {uid}: {e:?}")
                });
            } else {
                tracing::warn!("GroupPayment insufficient funds for {uid}");
            }
        }
        let _ = pay_models::set_contributions_status(&s.db, found.id, Some(c.member_id), "completed").await;
        bonus_sum += amount_dec;
        any_bonus = true;
    }
    if any_bonus && bonus_sum > Decimal::ZERO {
        let cents = (bonus_sum * Decimal::from(100))
            .round_dp(0)
            .to_string()
            .parse::<i64>()
            .unwrap_or(0);
        deliver_bonus(
            s,
            found.initiated_by.unwrap_or(0),
            request_id,
            vt_status,
            Some(cents),
        )
        .await;
    }
}
