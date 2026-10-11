//! Nomba wallet-funding endpoints. Mirrors
//! `transactions/nomba_views.py`: hosted-checkout funding init, bank
//! account lookup, dedicated virtual accounts, sessionId reconfirmation,
//! and the Nomba webhook (excluded from OpenAPI, like Django).
//!
//! All Nomba API calls go through the async `nomba-rs` client
//! (`super::nomba_gateway`); nothing here blocks the runtime.

use axum::{
    Json,
    body::Bytes,
    extract::State,
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};
use uuid::Uuid;

use crate::accounts::models as accounts_models;
use crate::auth::extractor::{auth_user, get_profile};
use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;
use crate::transactions::models as txn_models;
use crate::transactions::serializers::{AccountNameBody, InitializeFundingBody};
use crate::wallet::models::{self as wallet_models, cents_to_decimal, parse_cents};

use super::nomba_gateway;

type Resp = (StatusCode, Json<Value>);

fn first_present<'a>(data: &'a Value, keys: &[&str]) -> Option<&'a Value> {
    if !data.is_object() {
        return None;
    }
    for key in keys {
        if let Some(v) = data.get(*key) {
            if !(v.is_null() || v == &Value::String(String::new())) {
                return Some(v);
            }
        }
    }
    None
}

/// Webhook amount (naira) normalized to a 2dp decimal string, mirroring
/// Django's `Decimal(str(value))`.
fn naira_amount(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => {
            let d = s.trim().parse::<rust_decimal::Decimal>().ok()?;
            let mut q = d.round_dp(2);
            q.rescale(2);
            Some(q.to_string())
        }
        Value::Number(n) => {
            let d = n.to_string().parse::<rust_decimal::Decimal>().ok()?;
            let mut q = d.round_dp(2);
            q.rescale(2);
            Some(q.to_string())
        }
        _ => None,
    }
}

async fn fail_funding(db: &sqlx::PgPool, id: i64) {
    let _ = sqlx::query("UPDATE transactions_fundwallet SET status = 'FAILED' WHERE id = $1")
        .bind(id)
        .execute(db)
        .await;
}

#[utoipa::path(
    post,
    path = "/transactions/nomba/fund-wallet/",
    tag = "Nomba",
    summary = "Initialize wallet funding via Nomba",
    description = "Create a Nomba hosted checkout order to fund the user wallet (minimum: ₦100). Returns the hosted checkout URL.",
    request_body = InitializeFundingBody,
    responses((status = 200, description = "Checkout initialized"), (status = 400, description = "Below minimum or Nomba failure")),
    security(("bearer" = [])),
)]
pub async fn initialize_funding(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    // Mirrors DRF DecimalField(max_digits=12, decimal_places=2,
    // min_value=100.00) field errors.
    let raw = body.get("amount");
    let amount = match raw {
        None => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"amount": ["This field is required."]})),
            ))
        }
        Some(Value::String(text)) => match text.trim().parse::<rust_decimal::Decimal>() {
            Ok(d) => d,
            Err(_) => {
                return Ok((
                    StatusCode::BAD_REQUEST,
                    Json(json!({"amount": ["A valid number is required."]})),
                ))
            }
        },
        Some(Value::Number(n)) => match n.to_string().parse::<rust_decimal::Decimal>() {
            Ok(d) => d,
            Err(_) => {
                return Ok((
                    StatusCode::BAD_REQUEST,
                    Json(json!({"amount": ["A valid number is required."]})),
                ))
            }
        },
        _ => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"amount": ["A valid number is required."]})),
            ))
        }
    };
    if amount.scale() > 2 {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"amount": ["Ensure that there are no more than 2 decimal places."]})),
        ));
    }
    if amount.to_string().replace(['-', '.'], "").trim_start_matches('0').len() > 12 {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"amount": ["Ensure that there are no more than 12 digits in total."]})),
        ));
    }
    if amount < rust_decimal::Decimal::new(10000, 2) {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"amount": ["Ensure this value is greater than or equal to 100.00."]})),
        ));
    }
    let amount_cents = (amount * rust_decimal::Decimal::new(100, 0))
        .trunc()
        .to_string()
        .parse::<i64>()
        .unwrap_or(0);
    // Tier pre-check: refuse the checkout before the user pays when the
    // inflow would breach the cumulative cap (or the account is frozen).
    {
        let profile = get_profile(&s.db, user.id).await?;
        if profile.is_frozen {
            return Ok((StatusCode::FORBIDDEN, Json(json!({"success": false, "error": "Account frozen. Contact support."}))));
        }
        if let Some(limit) = crate::accounts::tier::limit_cents(&profile) {
            let totals = wallet_models::wallet_totals(&s.db, user.id).await?.map(|t| t.total_in_cents).unwrap_or(0);
            if totals + amount_cents > limit {
                return Ok((StatusCode::BAD_REQUEST, Json(json!({"success": false, "error": format!(
                    "Tier limit exceeded (max {} in). Upgrade your KYC tier before funding.",
                    crate::accounts::tier::limit_naira_display(limit)
                )}))));
            }
        }
    }
    let payment_reference = format!("BS-DEP-{uuid}", uuid = Uuid::new_v4());
    let now = now_str();
    txn_models::create_pending_funding(&s.db, user.id, amount_cents, &payment_reference, &now).await?;
    let (ok, result) =
        nomba_gateway::create_checkout_order(&s.config, &payment_reference, amount_cents, &user.email).await;
    // Look the row back up for the id (create returns no id).
    let fund_id: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM transactions_fundwallet WHERE payment_reference = $1",
    )
    .bind(&payment_reference)
    .fetch_optional(&s.db)
    .await?;
    if !ok {
        if let Some((id,)) = fund_id {
            fail_funding(&s.db, id).await;
        }
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"success": false, "error": result}))));
    }
    if let Some((id,)) = fund_id {
        let _ = sqlx::query(
            "UPDATE transactions_fundwallet SET gateway_reference = $1 WHERE id = $2",
        )
        .bind(&payment_reference)
        .bind(id)
        .execute(&s.db)
        .await;
    }
    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "checkout_url": result,
            "payment_reference": payment_reference,
            "amount": cents_to_decimal(amount_cents),
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/transactions/nomba/account-name/",
    tag = "Nomba",
    summary = "Resolve account name via Nomba",
    request_body = AccountNameBody,
    responses((status = 200, description = "Resolved"), (status = 404, description = "Could not resolve")),
    security(("bearer" = [])),
)]
pub async fn account_name(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers).await?;
    // Mirrors DRF required-field errors.
    let mut errors = serde_json::Map::new();
    let account_number = match body.get("account_number").and_then(|v| v.as_str()).map(|v| v.trim().to_string()).filter(|v| !v.is_empty()) {
        Some(v) => v,
        None => {
            errors.insert("account_number".to_string(), json!(["This field is required."]));
            String::new()
        }
    };
    let bank_code = match body.get("bank_code").and_then(|v| v.as_str()).map(|v| v.trim().to_string()).filter(|v| !v.is_empty()) {
        Some(v) => v,
        None => {
            errors.insert("bank_code".to_string(), json!(["This field is required."]));
            String::new()
        }
    };
    if !errors.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(Value::Object(errors))));
    }
    let result = nomba_gateway::lookup_account_name(&s.config, &account_number, &bank_code).await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((StatusCode::OK, Json(result)))
    } else {
        Ok((StatusCode::NOT_FOUND, Json(result)))
    }
}

#[utoipa::path(
    post,
    path = "/transactions/nomba/dva/assign/",
    tag = "Nomba",
    summary = "Assign Nomba dedicated virtual account",
    description = "Create a Nomba dedicated virtual account. Idempotent: returns the existing account when one is already assigned.",
    responses((status = 200, description = "Already assigned"), (status = 201, description = "Assigned"), (status = 400, description = "Nomba failure")),
    security(("bearer" = [])),
)]
pub async fn dva_assign(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    if let Some(existing) = accounts_models::find_nomba_dva_by_user(&s.db, user.id).await? {
        return Ok((
            StatusCode::OK,
            Json(json!({
                "already_exists": true,
                "account_number": existing.account_number,
                "account_name": existing.account_name,
                "bank_name": existing.bank_name,
                "account_ref": existing.account_ref,
                "active": existing.active,
            })),
        ));
    }
    // DVA identity is the user's NIN (KYC tier 2+), RSA-encrypted at
    // rest: decrypt for the Nomba call. No BVN anywhere on this path.
    if crate::accounts::tier::tier_of(&user) < 2 {
        return Err(AppError::bad_request(
            "NIN required for a dedicated account. Submit it at /accounts/kyc/nin/.",
        ));
    }
    let nin_enc = user.nin_encrypted.clone().unwrap_or_default();
    let nin = crate::accounts::crypto::decrypt_pin(&nin_enc, &s.config.pin_rsa_private_key_b64)
        .map_err(|_| AppError::bad_request("Could not read your NIN. Re-submit it at /accounts/kyc/nin/."))?;
    let full_name = format!("{} {}", user.surname, user.other_names).trim().to_string();
    let full_name = if full_name.is_empty() { user.email.clone() } else { full_name };
    let account_ref = format!("BS-NOMBA-DVA-{}", user.id);
    let (ok, result) =
        nomba_gateway::create_virtual_account(&s.config, &account_ref, &full_name, Some(nin)).await;
    if !ok {
        let msg = result.as_str().unwrap_or("Virtual account creation failed").to_string();
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"success": false, "error": msg}))));
    }
    let now = now_str();
    let account_number = result.get("bankAccountNumber").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let account_name = result.get("bankAccountName").and_then(|v| v.as_str()).unwrap_or(&full_name).to_string();
    let bank_name = result.get("bankName").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let active = !result.get("expired").and_then(|v| v.as_bool()).unwrap_or(false);
    let dva = accounts_models::create_nomba_dva(
        &s.db,
        user.id,
        &account_ref,
        &account_number,
        &account_name,
        &bank_name,
        active,
        &result.to_string(),
        &now,
    )
    .await?;
    let _ = crate::notifications::utils::send_notification(
        &s,
        user.id,
        &user.email,
        &user.other_names,
        "Virtual Account Ready",
        &format!("Your Nomba virtual account {} is ready to receive funds.", dva.account_number),
        "wallet",
        Some("BlueSea Mobile - Virtual Account Ready"),
        Default::default(),
    )
    .await;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "success": true,
            "account_number": dva.account_number,
            "account_name": dva.account_name,
            "bank_name": dva.bank_name,
            "account_ref": dva.account_ref,
            "active": dva.active,
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/transactions/nomba/dva/confirm/",
    tag = "Nomba",
    summary = "Confirm Nomba transaction by sessionId",
    responses((status = 200, description = "Confirmed"), (status = 400, description = "Missing id or Nomba failure")),
    security(("bearer" = [])),
)]
pub async fn dva_confirm(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers).await?;
    let session_id = body.get("session_id").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
    if session_id.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "session_id is required"}))));
    }
    let (ok, result) = nomba_gateway::confirm_transaction(&s.config, &session_id).await;
    if !ok {
        let msg = result.as_str().unwrap_or("Confirmation failed").to_string();
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"success": false, "error": msg}))));
    }
    Ok((StatusCode::OK, Json(json!({"success": true, "transaction": result}))))
}

// Nomba webhook — public, like Django (AllowAny, excluded from OpenAPI).
pub async fn webhook(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Resp {
    if body.len() > 1024 * 100 {
        tracing::warn!("nomba webhook payload too large {}", body.len());
        return (StatusCode::OK, Json(json!({"success": true})));
    }
    let payload = match nomba_gateway::verify_webhook(&s.config.nomba_signature_key, &body, &headers) {
        Ok(p) => p,
        Err(e) if e == "__too_large__" => {
            return (StatusCode::OK, Json(json!({"success": true})));
        }
        Err(e) => {
            tracing::error!("invalid nomba webhook signature: {e}");
            return (StatusCode::UNAUTHORIZED, Json(json!({"success": false, "error": e})));
        }
    };
    let Some(obj) = payload.as_object() else {
        return (StatusCode::OK, Json(json!({"success": true})));
    };
    let data = obj.get("data").filter(|v| v.is_object()).cloned().unwrap_or(Value::Null);
    let event_type = obj.get("event_type").and_then(|v| v.as_str()).unwrap_or("");
    tracing::info!("nomba webhook event={event_type}");
    // Handlers run inline for checkout/DVA credits (fast DB work); payout
    // mail is best-effort inside each handler, like Django.
    match event_type {
        "payment_success" => handle_payment_success(&s, &payload, &data).await,
        "payment_failed" => handle_payment_failed(&s, &payload, &data).await,
        "payout_success" => handle_payout_success(&s, &payload, &data).await,
        "payout_refund" => handle_payout_refund(&s, &payload, &data).await,
        _ => tracing::info!("nomba webhook ignored event_type={event_type}"),
    }
    (StatusCode::OK, Json(json!({"success": true})))
}

fn reference_of(payload: &Value, data: &Value) -> Option<String> {
    // Django checks every key against `data` first, then against `payload`.
    const KEYS: [&str; 6] = [
        "orderReference",
        "merchantTxRef",
        "merchant_tx_ref",
        "reference",
        "sessionId",
        "session_id",
    ];
    for key in KEYS {
        if let Some(v) = first_present(data, &[key]) {
            if let Some(s) = v.as_str().filter(|s| !s.is_empty()) {
                return Some(s.to_string());
            }
        }
    }
    for key in KEYS {
        if let Some(v) = first_present(payload, &[key]) {
            if let Some(s) = v.as_str().filter(|s| !s.is_empty()) {
                return Some(s.to_string());
            }
        }
    }
    None
}

async fn credit_wallet(
    s: &AppState,
    user_id: i64,
    amount_display: &str,
    description: &str,
    reference: &str,
) -> bool {
    let wallet = match wallet_models::get_by_user(&s.db, user_id).await.ok().flatten() {
        Some(w) => w,
        None => {
            tracing::error!("nomba credit: no wallet for user {user_id} ({reference})");
            return false;
        }
    };
    // External inflow: money already landed at Nomba, so it always credits
    // (no frozen/limit gate). Over-cap accounts freeze right after.
    let credited = wallet_models::credit_external_inflow(
        &s.db,
        &s.wallet_hub,
        wallet.id,
        user_id,
        amount_display,
        description,
        reference,
    )
    .await
    .is_ok();
    if credited {
        freeze_if_over_cap(s, user_id).await;
    }
    credited
}

/// Freeze when cumulative inflow crossed the tier cap (over-cap money that
/// arrived via DVA/checkout webhook). Unfreeze is admin-only.
async fn freeze_if_over_cap(s: &AppState, user_id: i64) {
    let profile = match get_profile(&s.db, user_id).await {
        Ok(p) => p,
        Err(_) => return,
    };
    if profile.is_frozen {
        return;
    }
    let Some(limit) = crate::accounts::tier::limit_cents(&profile) else {
        return;
    };
    let totals = match wallet_models::wallet_totals(&s.db, user_id).await {
        Ok(Some(t)) => t,
        _ => return,
    };
    if totals.total_in_cents > limit {
        let _ = wallet_models::freeze_account(
            &s.db,
            user_id,
            &format!(
                "Inflow {} exceeded tier limit {}.",
                totals.total_in_cents / 100,
                crate::accounts::tier::limit_naira_display(limit)
            ),
        )
        .await;
        tracing::warn!("froze user {user_id}: inflow over tier cap");
    }
}

async fn notify(
    s: &AppState,
    user_id: i64,
    title: &str,
    message: &str,
    notification_type: &str,
) {
    let Ok(profile) = get_profile(&s.db, user_id).await else {
        return;
    };
    let _ = crate::notifications::utils::send_notification(
        s,
        user_id,
        &profile.email,
        &profile.other_names,
        title,
        message,
        notification_type,
        Some(&format!("BlueSea Mobile - {title}")),
        Default::default(),
    )
    .await;
}

async fn complete_funding(s: &AppState, fund_id: i64) {
    let now = now_str();
    let _ = sqlx::query(
        "UPDATE transactions_fundwallet SET status = 'COMPLETED', completed_at = $1 WHERE id = $2",
    )
    .bind(crate::time::Ts(&now))
    .bind(fund_id)
    .execute(&s.db)
    .await;
}

async fn handle_payment_success(s: &AppState, payload: &Value, data: &Value) {
    let reference = reference_of(payload, data);
    let amount = ["amount", "transactionAmount", "settledAmount"]
        .iter()
        .filter_map(|k| first_present(data, &[k]))
        .find_map(naira_amount);

    // 1) Checkout funding: match FundWallet by our order reference.
    if let Some(ref reference) = reference {
        let fund: Option<txn_models::FundWallet> = sqlx::query_as(
            "SELECT id, CAST(amount AS TEXT) AS amount, payment_reference, gateway_reference,
                    status, created_at, completed_at, user_id
             FROM transactions_fundwallet WHERE payment_reference = $1",
        )
        .bind(reference)
        .fetch_optional(&s.db)
        .await
        .unwrap_or(None);
        if let Some(fund) = fund {
            if fund.status != "COMPLETED" {
                if let Some(amount) = amount.clone() {
                    // Best-effort idempotent credit, then completion + mail,
                    // mirroring Django (which completes even on repeats).
                    credit_wallet(s, fund.user_id, &amount, &format!("Nomba funding {reference}"), reference).await;
                    complete_funding(s, fund.id).await;
                    notify(
                        s,
                        fund.user_id,
                        "Wallet Funded",
                        &format!("₦{amount} received via Nomba. Your wallet has been credited."),
                        "payment_success",
                    )
                    .await;
                }
            }
            return;
        }
    }

    // 2) DVA inflow: match dedicated account by account number.
    let acct_num = ["accountNumber", "receiverAccountNumber", "destinationAccountNumber", "bankAccountNumber"]
        .iter()
        .filter_map(|k| first_present(data, &[k]))
        .find_map(|v| v.as_str().map(|v| v.to_string()));
    if let Some(ref acct_num) = acct_num {
        if let Ok(Some(dva)) = accounts_models::find_active_nomba_dva_by_number(&s.db, &acct_num).await {
            if let Some(amount) = amount {
                let session = ["sessionId", "session_id"]
                    .iter()
                    .filter_map(|k| first_present(data, &[k]))
                    .find_map(|v| v.as_str().map(|v| v.to_string()))
                    .unwrap_or_else(|| "W".to_string());
                let credit_ref = format!("BS-NOMBA-DVA-{}", reference.clone().unwrap_or(session));
                if credit_wallet(
                    s,
                    dva.user_id,
                    &amount,
                    &format!("Nomba DVA {}", dva.account_number),
                    &credit_ref,
                )
                .await
                {
                    notify(
                        s,
                        dva.user_id,
                        "Funds Received",
                        &format!("₦{amount} received via Nomba DVA {}. Your wallet has been credited.", dva.account_number),
                        "payment_success",
                    )
                    .await;
                    return;
                }
            }
        }
    }
    tracing::warn!("nomba payment_success matched nothing ref={reference:?} acct={}", acct_num.as_deref().unwrap_or(""));
}

async fn handle_payment_failed(s: &AppState, payload: &Value, data: &Value) {
    let Some(reference) = reference_of(payload, data) else {
        return;
    };
    let fund: Option<txn_models::FundWallet> = sqlx::query_as(
        "SELECT id, CAST(amount AS TEXT) AS amount, payment_reference, gateway_reference,
                status, created_at, completed_at, user_id
         FROM transactions_fundwallet WHERE payment_reference = $1",
    )
    .bind(&reference)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    let Some(fund) = fund else { return };
    if fund.status != "PENDING" {
        return;
    }
    fail_funding(&s.db, fund.id).await;
    notify(
        s,
        fund.user_id,
        "Funding Failed",
        &format!("Your Nomba wallet funding {reference} failed. No charge was made."),
        "payment_failed",
    )
    .await;
}

async fn handle_payout_success(s: &AppState, payload: &Value, data: &Value) {
    let Some(reference) = reference_of(payload, data) else {
        return;
    };
    let now = now_str();
    let _ = sqlx::query(
        "UPDATE payments_withdrawal SET status = 'successful', completed_at = $1
         WHERE payment_reference = $2 AND provider = 'nomba' AND status = 'pending'",
    )
    .bind(crate::time::Ts(&now))
    .bind(&reference)
    .execute(&s.db)
    .await;
}

async fn handle_payout_refund(s: &AppState, payload: &Value, data: &Value) {
    let Some(reference) = reference_of(payload, data) else {
        return;
    };
    let w = match crate::payments::models::find_withdrawal_by_reference_provider(&s.db, &reference, "nomba").await {
        Ok(w) => w,
        Err(e) => {
            tracing::error!("nomba payout_refund lookup failed: {e}");
            return;
        }
    };
    let Some(w) = w else { return };
    let now = now_str();
    if w.status != "successful" {
        let _ = sqlx::query(
            "UPDATE payments_withdrawal SET status = 'failed', completed_at = $1 WHERE id = $2",
        )
        .bind(crate::time::Ts(&now))
        .bind(w.id)
        .execute(&s.db)
        .await;
        return;
    }
    let reversal_ref: String = format!("REV-{reference}").chars().take(100).collect();
    let amount_cents = parse_cents(&w.amount).unwrap_or(0);
    if credit_wallet(
        s,
        w.user_id,
        &cents_to_decimal(amount_cents),
        &format!("Refund for Nomba payout {reference}"),
        &reversal_ref,
    )
    .await
    {
        let _ = sqlx::query(
            "UPDATE payments_withdrawal SET status = 'failed', completed_at = $1 WHERE id = $2",
        )
        .bind(crate::time::Ts(&now))
        .bind(w.id)
        .execute(&s.db)
        .await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;

    const NOMBA_SIG_KEY: &str = "test-nomba-signature-key";

    fn test_state(db: sqlx::PgPool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.nomba_signature_key = NOMBA_SIG_KEY.to_string();
        config.email_backend = "console".to_string();
        config.debug = true;
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
            support_hub: crate::support::hub::SupportHub::default(),
            plans_store: crate::plans_cache::PlansStore::default(),
            notification_hub: crate::notifications::hub::NotificationHub::default(),
        }
    }

    async fn memory_db() -> sqlx::PgPool {
        let pool = crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, password varchar(128) NOT NULL,
             last_login TIMESTAMPTZ NULL, is_superuser BOOLEAN NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined TIMESTAMPTZ NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active BOOLEAN NOT NULL,
             is_staff BOOLEAN NOT NULL, is_admin BOOLEAN NOT NULL, role varchar(200) NOT NULL, email_verified BOOLEAN NOT NULL,
             created_on TIMESTAMPTZ NOT NULL, pin_is_set BOOLEAN NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until TIMESTAMPTZ NULL, nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL, utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE, frozen_reason varchar(200) NULL, \"has_DVA\" BOOLEAN NOT NULL)",
            "CREATE TABLE wallet_wallet (id BIGSERIAL PRIMARY KEY, balance NUMERIC NOT NULL,
             locked_balance NUMERIC NOT NULL, total_in NUMERIC NOT NULL DEFAULT 0, total_out NUMERIC NOT NULL DEFAULT 0,  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             is_active BOOLEAN NOT NULL, user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE transactions_wallettransaction (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL, wallet_id bigint NOT NULL)",
            "CREATE TABLE transactions_fundwallet (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             payment_reference varchar(100) NOT NULL UNIQUE, gateway_reference varchar(100) NULL, status varchar(10) NOT NULL,
             created_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ NULL, user_id bigint NOT NULL)",
            "CREATE TABLE accounts_nombadedicatedaccount (id BIGSERIAL PRIMARY KEY, account_ref varchar(100) NOT NULL UNIQUE,
             account_number varchar(15) NOT NULL UNIQUE, account_name varchar(100) NOT NULL, bank_name varchar(50) NOT NULL DEFAULT '',
             active BOOLEAN NOT NULL DEFAULT TRUE, nomba_response JSONB NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE payments_withdrawal (id BIGSERIAL PRIMARY KEY, account_name varchar(100) NOT NULL,
             account_number varchar(10) NOT NULL, bank_code varchar(10) NOT NULL, bank_name varchar(50) NOT NULL,
             amount NUMERIC NOT NULL, status varchar(20) NOT NULL, payment_reference varchar(100) NULL UNIQUE,
             created_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ NULL, user_id bigint NOT NULL,
             recipient_code varchar(100) NULL, transfer_code varchar(100) NULL, provider varchar(20) NOT NULL DEFAULT 'paystack')",
            "CREATE TABLE notifications_notification (id BIGSERIAL PRIMARY KEY, title varchar(200) NOT NULL,
             message text NOT NULL, notification_type varchar(20) NOT NULL, is_read BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL,
             read_at TIMESTAMPTZ NULL, user_id bigint NOT NULL, broadcast_id bigint NULL)",
        ])
        .await;
        sqlx::query(
            "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
             is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, \"has_DVA\")
             VALUES ('x', FALSE, '', '', '2026-01-01 00:00:00', 'n@x.com', 'N', 'O', TRUE, FALSE, FALSE, 'user', TRUE, '2026-01-01 00:00:00', FALSE, 'NOMBA1', 0, FALSE)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (5000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', TRUE, 1)",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn signed(event_type: &str, data: Value) -> (HeaderMap, Bytes) {
        let payload = serde_json::json!({"event_type": event_type, "data": data});
        // Current timestamp: the webhook freshness window (5 min) rejects
        // stale replays, so tests must sign with now.
        let timestamp = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        let sig = nomba_rs::compute_signature(NOMBA_SIG_KEY, &payload, &timestamp);
        let mut headers = HeaderMap::new();
        headers.insert("nomba-signature", sig.parse().unwrap());
        headers.insert("nomba-timestamp", timestamp.parse().unwrap());
        let body = Bytes::from(serde_json::to_vec(&payload).unwrap());
        (headers, body)
    }

    #[test]
    fn reference_shapes() {
        let payload = serde_json::json!({"orderReference": "BS-DEP-1"});
        let data = serde_json::json!({"merchantTxRef": "M"});
        assert_eq!(reference_of(&payload, &data).as_deref(), Some("M"));
        assert_eq!(
            reference_of(&payload, &serde_json::json!({"sessionId": "S"})).as_deref(),
            Some("S")
        );
        assert!(reference_of(&payload, &serde_json::json!({})).is_some());
        assert!(reference_of(&serde_json::json!({}), &serde_json::json!({})).is_none());
        assert_eq!(naira_amount(&serde_json::json!("5000.00")).as_deref(), Some("5000.00"));
        assert_eq!(naira_amount(&serde_json::json!(5000)).as_deref(), Some("5000.00"));
        assert!(naira_amount(&serde_json::json!("abc")).is_none());
    }

    #[tokio::test]
    async fn oversized_body_acks() {
        let db = memory_db().await;
        let s = test_state(db);
        let big = Bytes::from(vec![b'x'; 1024 * 100 + 1]);
        let (status, body) = webhook(State(s), HeaderMap::new(), big).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body.0["success"], true);
    }

    #[tokio::test]
    async fn stale_timestamp_rejected_as_replay() {
        let db = memory_db().await;
        let s = test_state(db);
        let payload = serde_json::json!({"event_type": "payment_success", "data": {"orderReference": "BS-DEP-old"}});
        let timestamp = "2020-01-01T00:00:00Z".to_string();
        let sig = nomba_rs::compute_signature(NOMBA_SIG_KEY, &payload, &timestamp);
        let mut headers = HeaderMap::new();
        headers.insert("nomba-signature", sig.parse().unwrap());
        headers.insert("nomba-timestamp", timestamp.parse().unwrap());
        let body = Bytes::from(serde_json::to_vec(&payload).unwrap());
        let (status, body) = webhook(State(s), headers, body).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
        assert_eq!(body.0["success"], false);
    }

    #[tokio::test]
    async fn bad_signature_401s() {
        let db = memory_db().await;
        let s = test_state(db);
        let (mut headers, body) =
            signed("payment_success", serde_json::json!({"orderReference": "BS-DEP-1"}));
        headers.insert("nomba-signature", "nope".parse().unwrap());
        let (status, body) = webhook(State(s), headers, body).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
        assert_eq!(body.0["success"], false);
    }

    #[tokio::test]
    async fn checkout_success_credits_once() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        sqlx::query(
            "INSERT INTO transactions_fundwallet (amount, payment_reference, status, created_at, user_id)
             VALUES (10000, 'BS-DEP-test', 'PENDING', '2026-01-01 00:00:00', 1)",
        ).execute(&db).await.unwrap();
        let (headers, body) = signed(
            "payment_success",
            serde_json::json!({"orderReference": "BS-DEP-test", "amount": "10000.00"}),
        );
        let (status, _) = webhook(State(s.clone()), headers, body).await;
        assert_eq!(status, StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = 1")
                .fetch_one(&db).await.unwrap();
        assert_eq!(bal.0, "15000.00");
        // Duplicate delivery is a no-op on the same reference.
        let (headers, body) = signed(
            "payment_success",
            serde_json::json!({"orderReference": "BS-DEP-test", "amount": "10000.00"}),
        );
        let (status, _) = webhook(State(s.clone()), headers, body).await;
        assert_eq!(status, StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = 1")
                .fetch_one(&db).await.unwrap();
        assert_eq!(bal.0, "15000.00");
    }

    #[tokio::test]
    async fn checkout_failure_marks_failed() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        sqlx::query(
            "INSERT INTO transactions_fundwallet (amount, payment_reference, status, created_at, user_id)
             VALUES (10000, 'BS-DEP-fail', 'PENDING', '2026-01-01 00:00:00', 1)",
        ).execute(&db).await.unwrap();
        let (headers, body) = signed(
            "payment_failed",
            serde_json::json!({"orderReference": "BS-DEP-fail"}),
        );
        let (status, _) = webhook(State(s.clone()), headers, body).await;
        assert_eq!(status, StatusCode::OK);
        let st: (String,) =
            sqlx::query_as("SELECT status FROM transactions_fundwallet WHERE payment_reference = 'BS-DEP-fail'")
                .fetch_one(&db).await.unwrap();
        assert_eq!(st.0, "FAILED");
    }

    #[tokio::test]
    async fn dva_inflow_credits_by_account_number() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        sqlx::query(
            "INSERT INTO accounts_nombadedicatedaccount (user_id, account_ref, account_number, account_name, bank_name, active, created_at, updated_at)
             VALUES (1, 'BS-NOMBA-DVA-1', '9988776655', 'N O', 'Nomba', TRUE, '2026-01-01 00:00:00', '2026-01-01 00:00:00')",
        ).execute(&db).await.unwrap();
        let (headers, body) = signed(
            "payment_success",
            serde_json::json!({"accountNumber": "9988776655", "amount": "2500.00", "sessionId": "sess-1"}),
        );
        let (status, _) = webhook(State(s.clone()), headers, body).await;
        assert_eq!(status, StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = 1")
                .fetch_one(&db).await.unwrap();
        assert_eq!(bal.0, "7500.00");
    }

    #[tokio::test]
    async fn payout_success_and_refund() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        sqlx::query(
            "INSERT INTO payments_withdrawal (account_name, account_number, bank_code, bank_name, amount, status, payment_reference, created_at, user_id, provider)
             VALUES ('N', '0123456789', '058', 'B', 5000, 'pending', 'BS-WIT-1', '2026-01-01 00:00:00', 1, 'nomba')",
        ).execute(&db).await.unwrap();
        let (headers, body) = signed(
            "payout_success",
            serde_json::json!({"merchantTxRef": "BS-WIT-1"}),
        );
        let (status, _) = webhook(State(s.clone()), headers, body).await;
        assert_eq!(status, StatusCode::OK);
        let st: (String,) =
            sqlx::query_as("SELECT status FROM payments_withdrawal WHERE payment_reference = 'BS-WIT-1'")
                .fetch_one(&db).await.unwrap();
        assert_eq!(st.0, "successful");
        // Refund of a successful payout re-credits the wallet.
        let (headers, body) = signed(
            "payout_refund",
            serde_json::json!({"merchantTxRef": "BS-WIT-1"}),
        );
        let (status, _) = webhook(State(s.clone()), headers, body).await;
        assert_eq!(status, StatusCode::OK);
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = 1")
                .fetch_one(&db).await.unwrap();
        assert_eq!(bal.0, "10000.00");
        let st: (String,) =
            sqlx::query_as("SELECT status FROM payments_withdrawal WHERE payment_reference = 'BS-WIT-1'")
                .fetch_one(&db).await.unwrap();
        assert_eq!(st.0, "failed");
    }
}
