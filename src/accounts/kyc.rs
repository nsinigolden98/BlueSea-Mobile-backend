//! KYC tier evidence submission + status.
//!
//! Tiers derive from profile evidence (see `super::tier`):
//! T0 no phone · T1 phone · T2 +NIN · T3 +BVN · T4 +address+utility bill.
//! NIN/BVN arrive as plaintext over TLS, are 11-digit validated, then
//! RSA-encrypted at rest with the PIN key (same as `transaction_pin`).
//! The utility bill is a multipart image stored under `MEDIA_ROOT/kyc/`.

use axum::{
    Json,
    body::Bytes,
    extract::{Request, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};

use crate::accounts::tier;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

fn err(field: &str, message: &str) -> Value {
    json!({ field: [message] })
}

fn coerce_str(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

async fn me(s: &AppState, headers: HeaderMap) -> Result<crate::accounts::models::Profile, Resp> {
    let user = crate::auth::extractor::get_profile(
        &s.db,
        auth_user(State(s.clone()), headers)
            .await
            .map_err(|_| {
                (
                    StatusCode::UNAUTHORIZED,
                    Json(json!({"detail": "Authentication required"})),
                )
            })?
            .id,
    )
    .await
    .map_err(|_| {
        (
            StatusCode::UNAUTHORIZED,
            Json(json!({"detail": "Authentication required"})),
        )
    })?;
    Ok(user)
}

fn status_body(
    user: &crate::accounts::models::Profile,
    totals: Option<wallet_models::WalletTotals>,
) -> Value {
    let tier = tier::tier_of(user);
    let limit = tier::limit_cents(user);
    json!({
        "tier": tier,
        "in_limit": limit,
        "out_limit": limit,
        "in_limit_display": limit.map(tier::limit_naira_display),
        "total_in": totals.as_ref().map(|t| t.total_in_cents).unwrap_or(0),
        "total_out": totals.as_ref().map(|t| t.total_out_cents).unwrap_or(0),
        "missing": tier::missing_items(user),
        "has_nin": user.nin_encrypted.as_deref().map(|v| !v.is_empty()).unwrap_or(false),
        "has_bvn": user.bvn_encrypted.as_deref().map(|v| !v.is_empty()).unwrap_or(false),
        "has_address": user.house_address.as_deref().map(|v| !v.trim().is_empty()).unwrap_or(false),
        "has_utility_bill": user.utility_bill_image.as_deref().map(|v| !v.is_empty()).unwrap_or(false),
        "utility_bill_url": user.utility_bill_image.as_deref().map(|p| format!("/media/{p}")),
        "is_frozen": user.is_frozen,
        "frozen_reason": user.frozen_reason,
    })
}

#[utoipa::path(
    get,
    path = "/accounts/kyc/",
    tag = "KYC",
    summary = "KYC tier status",
    description = "Current tier, limits, lifetime in/out totals, missing items and frozen state.",
    responses((status = 200, description = "Tier status")),
    security(("bearer" = [])),
)]
pub async fn status(State(s): State<AppState>, headers: HeaderMap) -> Result<Resp, AppError> {
    let user = me(&s, headers).await.map_err(|e| AppError::new(e.0, e.1.0.to_string()))?;
    let totals = wallet_models::wallet_totals(&s.db, user.id).await?;
    Ok((StatusCode::OK, Json(status_body(&user, totals))))
}

async fn submit_encrypted(
    s: &AppState,
    headers: HeaderMap,
    body: Bytes,
    field: &str,
    column: &str,
) -> Result<Resp, AppError> {
    let user = me(s, headers).await.map_err(|e| AppError::new(e.0, e.1.0.to_string()))?;
    let value: Value = serde_json::from_slice(&body)
        .map_err(|_| AppError::bad_request("Invalid JSON"))?;
    let raw = coerce_str(value.get(field).unwrap_or(&Value::Null))
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .ok_or_else(|| AppError::new(StatusCode::BAD_REQUEST, err(field, "This field is required.").to_string()))?;
    // Accept plaintext 11-digit input (TLS transport); encrypt at rest.
    // An already-RSA-encrypted blob is detected by length and stored as-is
    // so mobile clients can pre-encrypt like the transaction PIN.
    let stored = if raw.len() > 64 {
        raw.clone()
    } else {
        if !tier::valid_nin_bvn(&raw) {
            return Err(AppError::new(StatusCode::BAD_REQUEST, err(field, "Must be 11 digits.").to_string()));
        }
        crate::accounts::crypto::encrypt_pin(&raw, &s.config.pin_rsa_private_key_b64)
            .map_err(|_| AppError::new(StatusCode::BAD_REQUEST, err(field, "Could not secure value.").to_string()))?
    };
    sqlx::query(&format!("UPDATE accounts_profile SET {column} = $1 WHERE id = $2"))
        .bind(&stored)
        .bind(user.id)
        .execute(&s.db)
        .await?;
    let user = crate::auth::extractor::get_profile(&s.db, user.id)
        .await
        .map_err(|_| AppError::internal("An error occurred"))?;
    let totals = wallet_models::wallet_totals(&s.db, user.id).await?;
    Ok((StatusCode::OK, Json(status_body(&user, totals))))
}

#[utoipa::path(
    post,
    path = "/accounts/kyc/nin/",
    tag = "KYC",
    summary = "Submit NIN (tier 2)",
    description = "11-digit NIN, RSA-encrypted at rest.",
    responses((status = 200, description = "Tier status"), (status = 400, description = "Invalid NIN")),
    security(("bearer" = [])),
)]
pub async fn submit_nin(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<Resp, AppError> {
    submit_encrypted(&s, headers, body, "nin", "nin_encrypted").await
}

#[utoipa::path(
    post,
    path = "/accounts/kyc/bvn/",
    tag = "KYC",
    summary = "Submit BVN (tier 3)",
    description = "11-digit BVN, RSA-encrypted at rest.",
    responses((status = 200, description = "Tier status"), (status = 400, description = "Invalid BVN")),
    security(("bearer" = [])),
)]
pub async fn submit_bvn(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<Resp, AppError> {
    submit_encrypted(&s, headers, body, "bvn", "bvn_encrypted").await
}

#[utoipa::path(
    post,
    path = "/accounts/kyc/address/",
    tag = "KYC",
    summary = "Submit house address (tier 4)",
    responses((status = 200, description = "Tier status"), (status = 400, description = "Invalid address")),
    security(("bearer" = [])),
)]
pub async fn submit_address(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<Resp, AppError> {
    let user = me(&s, headers).await.map_err(|e| AppError::new(e.0, e.1.0.to_string()))?;
    let value: Value = serde_json::from_slice(&body)
        .map_err(|_| AppError::bad_request("Invalid JSON"))?;
    let addr = coerce_str(value.get("house_address").unwrap_or(&Value::Null))
        .map(|v| v.trim().to_string())
        .filter(|v| v.len() >= 10)
        .ok_or_else(|| {
            AppError::new(StatusCode::BAD_REQUEST, err("house_address", "Must be at least 10 characters.").to_string())
        })?;
    if addr.len() > 500 {
        return Err(AppError::new(StatusCode::BAD_REQUEST, err(
            "house_address",
            "Ensure this field has no more than 500 characters.",
        ).to_string()));
    }
    sqlx::query("UPDATE accounts_profile SET house_address = $1 WHERE id = $2")
        .bind(&addr)
        .bind(user.id)
        .execute(&s.db)
        .await?;
    let user = crate::auth::extractor::get_profile(&s.db, user.id)
        .await
        .map_err(|_| AppError::internal("An error occurred"))?;
    let totals = wallet_models::wallet_totals(&s.db, user.id).await?;
    Ok((StatusCode::OK, Json(status_body(&user, totals))))
}

const BILL_EXTS: &[&str] = &["jpg", "jpeg", "png", "webp", "pdf"];

#[utoipa::path(
    post,
    path = "/accounts/kyc/utility-bill/",
    tag = "KYC",
    summary = "Upload utility bill (tier 4)",
    description = "Multipart image/PDF (max 5MB) as tier-4 address proof.",
    responses((status = 200, description = "Tier status"), (status = 400, description = "Invalid file")),
    security(("bearer" = [])),
)]
pub async fn upload_bill(State(s): State<AppState>, req: Request) -> Result<Resp, AppError> {
    use axum::extract::FromRequest;
    let headers = req.headers().clone();
    let user = me(&s, headers).await.map_err(|e| AppError::new(e.0, e.1.0.to_string()))?;
    let mut multipart = axum::extract::Multipart::from_request(req, &s)
        .await
        .map_err(|_| AppError::new(StatusCode::BAD_REQUEST, err("utility_bill", "Multipart upload required.").to_string()))?;
    let mut file: Option<(String, Vec<u8>)> = None;
    while let Ok(Some(field)) = multipart.next_field().await {
        let name = field.name().unwrap_or("").to_string();
        if name != "utility_bill" || field.file_name().is_none() {
            continue;
        }
        let fname = field.file_name().unwrap_or("bill").to_string();
        if let Ok(bytes) = field.bytes().await {
            file = Some((fname, bytes.to_vec()));
            break;
        }
    }
    let Some((filename, bytes)) = file else {
        return Err(AppError::new(StatusCode::BAD_REQUEST, err("utility_bill", "This field is required.").to_string()));
    };
    if bytes.is_empty() || bytes.len() > 5 * 1024 * 1024 {
        return Err(AppError::new(StatusCode::BAD_REQUEST, err("utility_bill", "File must be 1 byte to 5MB.").to_string()));
    }
    let ext = filename.rsplit('.').next().unwrap_or("").to_lowercase();
    if ext.is_empty() || ext.len() > 5 || !BILL_EXTS.contains(&ext.as_str()) {
        return Err(AppError::new(StatusCode::BAD_REQUEST, err("utility_bill", "JPG, PNG, WEBP or PDF only.").to_string()));
    }
    let stored = format!("kyc/{}.{}", uuid::Uuid::new_v4().simple(), ext);
    let path = std::path::Path::new(&s.config.media_root).join(&stored);
    if let Some(parent) = path.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|_| AppError::internal("An error occurred"))?;
    }
    tokio::fs::write(&path, &bytes)
        .await
        .map_err(|_| AppError::internal("An error occurred"))?;
    sqlx::query("UPDATE accounts_profile SET utility_bill_image = $1 WHERE id = $2")
        .bind(&stored)
        .bind(user.id)
        .execute(&s.db)
        .await?;
    let user = crate::auth::extractor::get_profile(&s.db, user.id)
        .await
        .map_err(|_| AppError::internal("An error occurred"))?;
    let totals = wallet_models::wallet_totals(&s.db, user.id).await?;
    Ok((StatusCode::OK, Json(status_body(&user, totals))))
}

#[cfg(test)]
mod tests {
    use super::*;

    async fn kyc_db() -> sqlx::PgPool {
        let pool = crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, password varchar(128) NOT NULL,
             last_login TIMESTAMPTZ NULL, is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
             first_name varchar(150) NOT NULL DEFAULT '', last_name varchar(150) NOT NULL DEFAULT '',
             date_joined TIMESTAMPTZ NOT NULL DEFAULT now(), email varchar(300) NOT NULL UNIQUE,
             surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL,
             is_active BOOLEAN NOT NULL DEFAULT TRUE,
             is_staff BOOLEAN NOT NULL DEFAULT FALSE, is_admin BOOLEAN NOT NULL DEFAULT FALSE,
             role varchar(200) NOT NULL DEFAULT 'user', email_verified BOOLEAN NOT NULL DEFAULT TRUE,
             created_on TIMESTAMPTZ NOT NULL DEFAULT now(), pin_is_set BOOLEAN NOT NULL DEFAULT FALSE,
             transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL DEFAULT 0,
             pin_locked_until TIMESTAMPTZ NULL,
             nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL,
             utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
             frozen_reason varchar(200) NULL, \"has_DVA\" BOOLEAN NOT NULL DEFAULT FALSE)",
            "CREATE TABLE transactions_wallettransaction (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL, wallet_id bigint NOT NULL)",
            "CREATE TABLE wallet_wallet (id BIGSERIAL PRIMARY KEY, balance NUMERIC NOT NULL DEFAULT 0,
             locked_balance NUMERIC NOT NULL DEFAULT 0, total_in NUMERIC NOT NULL DEFAULT 0,
             total_out NUMERIC NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
             updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), is_active BOOLEAN NOT NULL DEFAULT TRUE,
             user_id bigint NOT NULL UNIQUE)",
        ])
        .await;
        sqlx::query(
            "INSERT INTO accounts_profile (password, email, surname, other_names, referral_code)
             VALUES ('x', 'k@t.com', 'S', 'O', 'KYCT01')",
        )
        .execute(&pool)
        .await
        .unwrap();
        sqlx::query("INSERT INTO wallet_wallet (user_id) VALUES (1)")
            .execute(&pool)
            .await
            .unwrap();
        pool
    }

    fn state(db: sqlx::PgPool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        // Fresh RSA key for the roundtrip (encrypt + decrypt in-test).
        let mut rng = rand::thread_rng();
        let key = rsa::RsaPrivateKey::new(&mut rng, 2048).unwrap();
        use rsa::pkcs8::EncodePrivateKey;
        let pem = key.to_pkcs8_pem(rsa::pkcs8::LineEnding::LF).unwrap().to_string();
        config.pin_rsa_private_key_b64 =
            base64::Engine::encode(&base64::engine::general_purpose::STANDARD, pem.as_bytes());
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
            support_hub: crate::support::hub::SupportHub::default(),
            notification_hub: crate::notifications::hub::NotificationHub::default(),
            plans_store: crate::plans_cache::PlansStore::default(),
        }
    }

    #[tokio::test]
    async fn nin_bvn_roundtrip_and_tier_climb() {
        let db = kyc_db().await;
        let s = state(db.clone());
        let headers = HeaderMap::new();
        // Unauthenticated without a token.
        assert!(me(&s, headers.clone()).await.is_err());

        // NIN stored encrypted, tier climbs to 2 (phone set first).
        sqlx::query("UPDATE accounts_profile SET phone = '0801' WHERE id = 1")
            .execute(&db)
            .await
            .unwrap();
        // Direct submit path needs auth; exercise validation + encryption here.
        assert!(tier::valid_nin_bvn("12345678901"));
        let enc = crate::accounts::crypto::encrypt_pin("12345678901", &s.config.pin_rsa_private_key_b64).unwrap();
        assert_ne!(enc, "12345678901");
        let dec = crate::accounts::crypto::decrypt_pin(&enc, &s.config.pin_rsa_private_key_b64).unwrap();
        assert_eq!(dec, "12345678901");
        sqlx::query("UPDATE accounts_profile SET nin_encrypted = $1 WHERE id = 1")
            .bind(&enc)
            .execute(&db)
            .await
            .unwrap();
        let user = crate::auth::extractor::get_profile(&db, 1).await.unwrap();
        assert_eq!(tier::tier_of(&user), 2);
        let body = status_body(&user, wallet_models::wallet_totals(&db, 1).await.unwrap());
        assert_eq!(body["tier"], 2);
        assert_eq!(body["in_limit"], tier::T2_LIMIT_CENTS);
    }

    #[tokio::test]
    async fn limits_and_freeze() {
        let db = kyc_db().await;
        let hub = crate::wallet::hub::WalletHub::default();
        // T0 (no phone): 100k in-cap.
        let over = wallet_models::credit(&db, &hub, 1, 1, "100001", "big", Some("cap-1")).await;
        assert!(matches!(over, Err(crate::wallet::models::WalletError::LimitExceeded { .. })));
        assert!(wallet_models::credit(&db, &hub, 1, 1, "50000", "ok", Some("cap-2")).await.is_ok());
        // External inflow bypasses the gate but trips the freeze.
        assert!(wallet_models::credit_external_inflow(&db, &hub, 1, 1, "200000", "dva", "cap-3").await.is_ok());
        // Frozen blocks normal movement both ways.
        wallet_models::freeze_account(&db, 1, "over tier limit").await.unwrap();
        assert!(matches!(
            wallet_models::credit(&db, &hub, 1, 1, "10", "x", Some("cap-4")).await,
            Err(crate::wallet::models::WalletError::Frozen)
        ));
        assert!(matches!(
            wallet_models::lock_amount(&db, 1, 1, 100, Some(tier::T0_T1_LIMIT_CENTS)).await,
            Err(crate::wallet::models::WalletError::Frozen)
        ));
        let totals = wallet_models::wallet_totals(&db, 1).await.unwrap().unwrap();
        assert_eq!((totals.total_in_cents, totals.frozen), (250_000_00, true));
    }
}
