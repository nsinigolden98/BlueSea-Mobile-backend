//! Paystack webhook. Mirrors `transactions/views.py::PaymentWebhook`
//! (excluded from the OpenAPI schema, like Django's `extend_schema(exclude=True)`):
//! HMAC-SHA512 signature check, DVA assign events, transfer events
//! (withdrawal status + refunds), and `charge.success` for both DVA
//! transfers (with ₦5 fee) and checkout funding.

use axum::{Json, body::Bytes, extract::State, http::{HeaderMap, StatusCode}};
use hmac::{Hmac, Mac};
use serde_json::{Value, json};
use sha2::Sha512;

use crate::accounts::models as accounts_models;
use crate::auth::extractor::get_profile;
use crate::error::AppError;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::state::AppState;
use crate::transactions::models as txn_models;
use crate::wallet::models as wallet_models;

fn verify_signature(secret: &str, body: &[u8], signature: &str) -> bool {
    if secret.is_empty() || signature.is_empty() {
        return false;
    }
    let mut mac = match Hmac::<Sha512>::new_from_slice(secret.as_bytes()) {
        Ok(m) => m,
        Err(_) => return false,
    };
    mac.update(body);
    let expect = hex::encode(mac.finalize().into_bytes());
    bool::from(subtle::ConstantTimeEq::ct_eq(
        expect.as_bytes(),
        signature.as_bytes(),
    ))
}

fn bad(status: StatusCode, body: Value) -> (StatusCode, Json<Value>) {
    (status, Json(body))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;

    const WEBHOOK_SECRET: &str = "testsecret";

    fn test_state(db: sqlx::SqlitePool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.paystack_secret_key = WEBHOOK_SECRET.to_string();
        config.email_backend = "console".to_string();
        config.debug = true;
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
        }
    }

    async fn memory_db() -> sqlx::SqlitePool {
        let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        sqlx::query(
            "CREATE TABLE accounts_profile (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, password varchar(128) NOT NULL,
             last_login datetime NULL, is_superuser bool NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined datetime NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active bool NOT NULL,
             is_staff bool NOT NULL, is_admin bool NOT NULL, role varchar(200) NOT NULL, email_verified bool NOT NULL,
             created_on datetime NOT NULL, pin_is_set bool NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until datetime NULL, has_DVA bool NOT NULL)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "CREATE TABLE wallet_wallet (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, balance decimal NOT NULL,
             locked_balance decimal NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL,
             is_active bool NOT NULL, user_id bigint NOT NULL UNIQUE)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "CREATE TABLE transactions_wallettransaction (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, amount decimal NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at datetime NOT NULL, wallet_id bigint NOT NULL)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "CREATE TABLE transactions_fundwallet (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, amount decimal NOT NULL,
             payment_reference varchar(100) NOT NULL UNIQUE, gateway_reference varchar(100) NULL, status varchar(10) NOT NULL,
             created_at datetime NOT NULL, completed_at datetime NULL, user_id bigint NOT NULL)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "CREATE TABLE notifications_notification (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, title varchar(200) NOT NULL,
             message text NOT NULL, notification_type varchar(20) NOT NULL, is_read bool NOT NULL, created_at datetime NOT NULL,
             read_at datetime NULL, user_id bigint NOT NULL, broadcast_id bigint NULL)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
             is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, has_DVA)
             VALUES ('x', 0, '', '', '2026-01-01 00:00:00', 'w@example.com', 'W', 'X', 1, 0, 0, 'user', 1, '2026-01-01 00:00:00', 0, 'ABCDEF', 0, 0)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (5000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1, 1)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO transactions_fundwallet (amount, payment_reference, status, created_at, user_id)
             VALUES (10000, 'BS-DEP-test', 'PENDING', '2026-01-01 00:00:00', 1)",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn signed_payload(payload: &Value) -> (HeaderMap, Bytes) {
        let body = serde_json::to_vec(payload).unwrap();
        let mut mac = Hmac::<Sha512>::new_from_slice(WEBHOOK_SECRET.as_bytes()).unwrap();
        mac.update(&body);
        let sig = hex::encode(mac.finalize().into_bytes());
        let mut headers = HeaderMap::new();
        headers.insert("x-paystack-signature", sig.parse().unwrap());
        (headers, Bytes::from(body))
    }

    fn charge_success(reference: &str, kobo: i64) -> Value {
        serde_json::json!({
            "event": "charge.success",
            "data": {"reference": reference, "amount": kobo, "authorization": {"channel": "card"}}
        })
    }

    #[tokio::test]
    async fn checkout_charge_credits_once_then_404s() {
        let db = memory_db().await;
        let s = test_state(db.clone());

        // 1. bad signature -> 401
        let (headers, body) = signed_payload(&charge_success("BS-DEP-test", 1_000_000));
        let mut bad_headers = headers.clone();
        bad_headers.insert("x-paystack-signature", "nope".parse().unwrap());
        let resp = dispatch(State(s.clone()), bad_headers, body.clone()).await;
        assert_eq!(resp.0, StatusCode::UNAUTHORIZED);

        // 2. valid charge.success for ₦10000 -> 200, wallet 5000 -> 15000
        let resp = dispatch(State(s.clone()), headers, body).await;
        assert_eq!(resp.0, StatusCode::OK);
        assert_eq!(resp.1 .0["success"], true);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = 1")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(bal.0, "15000");
        let status: (String,) =
            sqlx::query_as("SELECT status FROM transactions_fundwallet WHERE payment_reference = 'BS-DEP-test'")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(status.0, "COMPLETED");
        let notes: (i64,) =
            sqlx::query_as("SELECT COUNT(*) FROM notifications_notification WHERE user_id = 1")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(notes.0, 1);

        // 3. duplicate webhook -> 404 invalid reference (Django parity)
        let (headers, body) = signed_payload(&charge_success("BS-DEP-test", 1_000_000));
        let resp = dispatch(State(s.clone()), headers, body).await;
        assert_eq!(resp.0, StatusCode::NOT_FOUND);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE id = 1")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(bal.0, "15000");
    }

    #[tokio::test]
    async fn amount_mismatch_fails_funding() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        let (headers, body) = signed_payload(&charge_success("BS-DEP-test", 999_998));
        let resp = dispatch(State(s.clone()), headers, body).await;
        assert_eq!(resp.0, StatusCode::BAD_REQUEST);
        let status: (String,) =
            sqlx::query_as("SELECT status FROM transactions_fundwallet WHERE payment_reference = 'BS-DEP-test'")
                .fetch_one(&db)
                .await
                .unwrap();
        assert_eq!(status.0, "FAILED");
    }
}

pub async fn paystack_webhook(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<impl axum::response::IntoResponse, AppError> {
    Ok(dispatch(State(s), headers, body).await)
}

async fn dispatch(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> (StatusCode, Json<Value>) {
    let signature = headers
        .get("x-paystack-signature")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if !verify_signature(&s.config.paystack_secret_key, &body, signature) {
        tracing::error!("Invalid Paystack signature");
        return bad(
            StatusCode::UNAUTHORIZED,
            json!({"success": false, "error": "Invalid signature"}),
        );
    }
    let data: Value = match serde_json::from_slice(&body) {
        Ok(v) => v,
        Err(e) => {
            return bad(
                StatusCode::INTERNAL_SERVER_ERROR,
                json!({"success": false, "error": e.to_string()}),
            )
        }
    };
    let event = data.get("event").and_then(|v| v.as_str()).unwrap_or("");

    if matches!(
        event,
        "dedicatedaccount.assign.success"
            | "dedicatedaccount.assign.failed"
            | "customeridentification.success"
            | "customeridentification.failed"
    ) {
        return handle_dva_assign_events(&s, event, &data).await;
    }

    if matches!(event, "transfer.success" | "transfer.failed" | "transfer.reversed") {
        return handle_transfer_events(&s, event, &data).await;
    }

    if event == "charge.success" {
        return handle_charge_success(&s, &data).await;
    }

    bad(StatusCode::OK, json!({"success": true}))
}

// ---------- DVA assign / identification events ----------

async fn handle_dva_assign_events(
    s: &AppState,
    event: &str,
    data: &Value,
) -> (StatusCode, Json<Value>) {
    let payload = data.get("data").cloned().unwrap_or(Value::Null);

    if event == "dedicatedaccount.assign.success" {
        let dedicated = payload.get("dedicated_account").cloned().unwrap_or(Value::Null);
        let customer = payload.get("customer").cloned().unwrap_or(Value::Null);
        let email = customer.get("email").and_then(|v| v.as_str()).unwrap_or("");
        let dva = accounts_models::find_dva_by_user_email(&s.db, email).await;
        let Ok(Some(dva)) = dva else {
            // Mirror Django: only rows matched by customer email are updated.
            return bad(StatusCode::OK, json!({"success": true}));
        };
        let now = crate::time::now_str();
        let payload_json = serde_json::to_string(&payload).unwrap_or_default();
        let upd = accounts_models::mark_dva_assigned(
            &s.db,
            dva.id,
            dedicated.get("active").and_then(|v| v.as_bool()).unwrap_or(true),
            &payload_json,
            dedicated.get("account_number").and_then(|v| v.as_str()),
            dedicated.get("account_name").and_then(|v| v.as_str()),
            customer.get("customer_code").and_then(|v| v.as_str()).unwrap_or(""),
            dedicated.get("id").and_then(|v| v.as_i64()),
            customer.get("id").and_then(|v| v.as_i64()),
            &now,
        )
        .await;
        if let Err(e) = upd {
            tracing::error!("DVA webhook handling error {event}: {e}");
            return bad(StatusCode::OK, json!({"success": true}));
        }
        let _ = accounts_models::set_has_dva(&s.db, dva.user_id).await;
        tracing::info!("DVA webhook {event} updated {} for {email}", dva.account_number);
        if let Ok(user) = get_profile(&s.db, dva.user_id).await {
            let number = dedicated
                .get("account_number")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let _ = send_notification(
                s,
                user.id,
                &user.email,
                &user.other_names,
                "Dedicated Account Active",
                &format!("Your Wema DVA {number} is now active and ready to receive funds."),
                "dva_assigned",
                Some("BlueSea Mobile - DVA Active"),
                NotifyContext::default(),
            )
            .await;
        }
    } else if event == "dedicatedaccount.assign.failed" {
        tracing::warn!(
            "DVA assign failed: customer_code={} data={}",
            payload.get("customer_code").and_then(|v| v.as_str()).unwrap_or(""),
            payload
        );
    }

    if matches!(
        event,
        "customeridentification.success" | "customeridentification.failed"
    ) {
        tracing::info!(
            "Customer identification {event} for customer_code={}: {}",
            payload.get("customer_code").and_then(|v| v.as_str()).unwrap_or(""),
            payload.get("reason").and_then(|v| v.as_str()).unwrap_or("")
        );
    }
    bad(StatusCode::OK, json!({"success": true}))
}

// ---------- transfer events (withdrawals) ----------

async fn handle_transfer_events(
    s: &AppState,
    event: &str,
    data: &Value,
) -> (StatusCode, Json<Value>) {
    let payload = data.get("data").cloned().unwrap_or(Value::Null);
    let reference = payload.get("reference").and_then(|v| v.as_str()).unwrap_or("");
    if reference.is_empty() {
        return bad(StatusCode::OK, json!({"success": true}));
    }
    // payments_withdrawal lives in the payments app (ported later); the table
    // already exists, so the webhook updates it directly via SQL.
    let row: Option<(i64, i64, String, String)> = sqlx::query_as(
        "SELECT id, user_id, CAST(amount AS TEXT), status FROM payments_withdrawal WHERE payment_reference = ?",
    )
    .bind(reference)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    let Some((id, user_id, amount_raw, _status)) = row else {
        tracing::warn!("Transfer webhook: Withdrawal with reference {reference} not found");
        return bad(StatusCode::OK, json!({"success": true}));
    };

    let now = crate::time::now_str();
    let new_status = if event == "transfer.success" { "successful" } else { "failed" };
    if sqlx::query("UPDATE payments_withdrawal SET status = ?, completed_at = ? WHERE id = ?")
        .bind(new_status)
        .bind(&now)
        .bind(id)
        .execute(&s.db)
        .await
        .is_err()
    {
        tracing::error!("Transfer webhook handling error {event}");
        return bad(StatusCode::OK, json!({"success": true}));
    }

    if event == "transfer.success" {
        tracing::info!("Transfer success: Withdrawal {reference} completed");
        return bad(StatusCode::OK, json!({"success": true}));
    }

    // failed / reversed: refund the wallet (mirrors withdrawal.user.wallet.credit).
    let wallet: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM wallet_wallet WHERE user_id = ?")
            .bind(user_id)
            .fetch_optional(&s.db)
            .await
            .unwrap_or(None);
    if let Some((wallet_id,)) = wallet {
        let kind = if event == "transfer.failed" { "REFUND" } else { "REVERSAL" };
        let _ = wallet_models::credit(
            &s.db,
            &s.wallet_hub,
            wallet_id,
            user_id,
            &amount_raw,
            &format!("Refund for {failed} withdrawal {reference}", failed = event.strip_prefix("transfer.").unwrap_or(event)),
            Some(&format!("{reference}-{kind}")),
        )
        .await;
    }
    tracing::warn!("Transfer {event}: Withdrawal {reference} refunded");
    bad(StatusCode::OK, json!({"success": true}))
}

// ---------- charge.success ----------

async fn handle_charge_success(s: &AppState, data: &Value) -> (StatusCode, Json<Value>) {
    let payload = data.get("data").cloned().unwrap_or(Value::Null);
    let paystack_reference = payload.get("reference").and_then(|v| v.as_str()).unwrap_or("");
    let kobo = payload.get("amount").and_then(|v| v.as_i64()).unwrap_or(0);
    // Kobo and naira-cents are numerically identical (₦1 = 100 of either).
    let amount_cents = kobo;
    let auth = payload.get("authorization").cloned().unwrap_or(Value::Null);
    let channel = auth
        .get("channel")
        .and_then(|v| v.as_str())
        .or_else(|| payload.get("channel").and_then(|v| v.as_str()))
        .unwrap_or("");

    if channel == "dedicated_nuban" {
        return handle_dva_charge(s, &payload, &auth, paystack_reference, amount_cents).await;
    }
    handle_checkout_charge(s, paystack_reference, amount_cents).await
}

async fn handle_dva_charge(
    s: &AppState,
    payload: &Value,
    auth: &Value,
    paystack_reference: &str,
    amount_cents: i64,
) -> (StatusCode, Json<Value>) {
    let customer_code = payload
        .get("customer")
        .and_then(|v| v.as_object())
        .and_then(|m| m.get("customer_code"))
        .and_then(|v| v.as_str())
        .or_else(|| payload.get("customer_code").and_then(|v| v.as_str()))
        .unwrap_or("");
    let reference = format!("BS-DVA-DEP-{paystack_reference}");

    if txn_models::reference_exists(&s.db, &reference)
        .await
        .unwrap_or(false)
    {
        tracing::info!("DVA webhook duplicate reference {reference} ignored");
        return bad(StatusCode::OK, json!({"success": true}));
    }

    // Django only resolves by customer_code; without one it logs and acks
    // (the account-number fallback branch returns before crediting).
    if customer_code.is_empty() {
        tracing::warn!(
            "DVA charge.success no matching DVA customer_code= acct={} ref={}",
            auth.get("receiver_bank_account_number").and_then(|v| v.as_str()).unwrap_or(""),
            reference
        );
        return bad(StatusCode::OK, json!({"success": true}));
    }
    let dva = accounts_models::find_dva_by_customer_code(&s.db, customer_code)
        .await
        .unwrap_or(None);
    let Some(dva) = dva else {
        return bad(
            StatusCode::INTERNAL_SERVER_ERROR,
            json!({"success": false, "error": "DVA not found"}),
        );
    };

    let _ = accounts_models::set_has_dva(&s.db, dva.user_id).await;
    let wallet: Option<(i64,)> = sqlx::query_as("SELECT id FROM wallet_wallet WHERE user_id = ?")
        .bind(dva.user_id)
        .fetch_optional(&s.db)
        .await
        .unwrap_or(None);
    let Some((wallet_id,)) = wallet else {
        tracing::error!("DVA wallet not found for reference {reference}");
        return bad(
            StatusCode::NOT_FOUND,
            json!({"success": false, "error": "Wallet not found"}),
        );
    };

    // ₦5.00 Paystack fee, like Django's `amount - Decimal("5.00")`.
    let net_cents = amount_cents - 500;
    let sender_name = auth.get("sender_name").and_then(|v| v.as_str()).unwrap_or("");
    let sender_bank = auth.get("sender_bank_name").and_then(|v| v.as_str()).unwrap_or("");
    let acct = dva.dva_account_number.clone().unwrap_or_default();
    let credited = wallet_models::credit(
        &s.db,
        &s.wallet_hub,
        wallet_id,
        dva.user_id,
        &wallet_models::cents_to_decimal(net_cents),
        &format!("DVA Wema {acct} from {sender_name} {sender_bank} via {}", dva.bank_name),
        Some(&reference),
    )
    .await;
    match credited {
        Ok(_) => {
            tracing::info!("DVA credited {net_cents}c to user {} ref={reference} account={acct}", dva.user_id);
            if let Ok(user) = get_profile(&s.db, dva.user_id).await {
                let amount_disp = wallet_models::format_naira(net_cents);
                let _ = send_notification(
                    s,
                    user.id,
                    &user.email,
                    &user.other_names,
                    "Dedicated Virtual Account Deposit Received",
                    &format!(
                        "{amount_disp} received via Wema DVA {acct} from {sender_bank} in {sender_name} (ref {reference}) — your BlueSea Mobile wallet has been credited."
                    ),
                    "payment_success",
                    Some("BlueSea Mobile- Dedicated Virtual Account Deposit Received"),
                    NotifyContext::default(),
                )
                .await;
            }
            bad(StatusCode::OK, json!({"success": true, "message": "DVA transfer credited"}))
        }
        Err(e) => {
            tracing::error!("DVA webhook error {reference}: {e:?}");
            bad(
                StatusCode::INTERNAL_SERVER_ERROR,
                json!({"success": false, "error": format!("{e:?}")}),
            )
        }
    }
}

async fn handle_checkout_charge(
    s: &AppState,
    paystack_reference: &str,
    amount_cents: i64,
) -> (StatusCode, Json<Value>) {
    let funding = txn_models::find_pending_funding(&s.db, paystack_reference).await;
    let Ok(Some(funding)) = funding else {
        return bad(
            StatusCode::NOT_FOUND,
            json!({"success": false, "error": "Invalid payment reference"}),
        );
    };
    let wallet: Option<(i64, String)> = sqlx::query_as(
        "SELECT id, CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = ?",
    )
    .bind(funding.user_id)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    let Some((wallet_id, balance_raw)) = wallet else {
        tracing::error!("Wallet not found for funding {paystack_reference}");
        let _ = sqlx::query("UPDATE transactions_fundwallet SET status = 'FAILED' WHERE id = ?")
            .bind(funding.id)
            .execute(&s.db)
            .await;
        return bad(
            StatusCode::NOT_FOUND,
            json!({"success": false, "error": "Wallet not found"}),
        );
    };

    let request_cents = wallet_models::parse_cents(&funding.amount).unwrap_or(-1);
    if (request_cents - amount_cents).abs() > 1 {
        tracing::error!("Amount mismatch for {paystack_reference}");
        let _ = sqlx::query("UPDATE transactions_fundwallet SET status = 'FAILED' WHERE id = ?")
            .bind(funding.id)
            .execute(&s.db)
            .await;
        return bad(
            StatusCode::BAD_REQUEST,
            json!({"success": false, "error": format!(
                "Amount mismatch. Expected {}, got {}",
                wallet_models::cents_to_decimal(request_cents),
                wallet_models::cents_to_decimal(amount_cents)
            )}),
        );
    }

    let balance_cents = match wallet_models::parse_cents(&balance_raw) {
        Ok(c) => c,
        Err(_) => {
            let _ = sqlx::query("UPDATE transactions_fundwallet SET status = 'FAILED' WHERE id = ?")
                .bind(funding.id)
                .execute(&s.db)
                .await;
            return bad(
                StatusCode::BAD_REQUEST,
                json!({"success": false, "error": "Corrupt wallet balance"}),
            );
        }
    };
    let new_balance = balance_cents + amount_cents;
    let now = crate::time::now_str();
    let mut tx = match s.db.begin().await {
        Ok(t) => t,
        Err(e) => {
            return bad(
                StatusCode::INTERNAL_SERVER_ERROR,
                json!({"success": false, "error": e.to_string()}),
            )
        }
    };
    let steps = async {
        sqlx::query("UPDATE transactions_fundwallet SET status = 'PROCESSING' WHERE id = ?")
            .bind(funding.id)
            .execute(&mut *tx)
            .await?;
        sqlx::query("UPDATE wallet_wallet SET balance = ?, updated_at = ? WHERE id = ?")
            .bind(wallet_models::cents_to_decimal(new_balance))
            .bind(&now)
            .bind(wallet_id)
            .execute(&mut *tx)
            .await?;
        txn_models::record_tx(
            &mut tx,
            wallet_id,
            amount_cents,
            "CREDIT",
            "Wallet Funding",
            paystack_reference,
            &now,
        )
        .await?;
        sqlx::query(
            "UPDATE transactions_fundwallet SET status = 'COMPLETED', completed_at = ? WHERE id = ?",
        )
        .bind(&now)
        .bind(funding.id)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok::<(), sqlx::Error>(())
    }
    .await;
    if let Err(e) = steps {
        let _ = sqlx::query("UPDATE transactions_fundwallet SET status = 'FAILED' WHERE id = ?")
            .bind(funding.id)
            .execute(&s.db)
            .await;
        return bad(
            StatusCode::BAD_REQUEST,
            json!({"success": false, "error": e.to_string()}),
        );
    }

    if let Ok(user) = get_profile(&s.db, funding.user_id).await {
        let amount_disp = wallet_models::format_naira(amount_cents);
        let _ = send_notification(
            s,
            user.id,
            &user.email,
            &user.other_names,
            "Deposite To BlueSea Mobile Account",
            &format!("Successful Deposite of {amount_disp}"),
            "payment_success",
            Some("BlueSea Mobile - Checkout Deposite"),
            NotifyContext::default(),
        )
        .await;
    }
    bad(
        StatusCode::OK,
        json!({
            "success": true,
            "message": "Payment processed successfully",
            "old_balance": balance_raw,
            "new_balance": wallet_models::cents_to_decimal(new_balance),
        }),
    )
}
