//! Database row types for the accounts app.
//! Mirrors `accounts/models.py` — table shapes only, no request/response DTOs
//! (those live in `serializers.rs`, like DRF serializers).

use serde::Serialize;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow, Serialize)]
pub struct Profile {
    pub id: i64,
    pub password: String,
    pub last_login: Option<crate::time::NaiveUtc>,
    pub is_superuser: bool,
    pub first_name: String,
    pub last_name: String,
    pub date_joined: crate::time::NaiveUtc,
    pub email: String,
    pub surname: String,
    pub other_names: String,
    pub phone: Option<String>,
    pub image: Option<String>,
    pub verification_code: Option<String>,
    pub is_active: bool,
    pub is_staff: bool,
    pub is_admin: bool,
    pub role: String,
    pub email_verified: bool,
    pub created_on: crate::time::NaiveUtc,
    pub pin_is_set: bool,
    pub transaction_pin: Option<String>,
    pub referral_code: String,
    pub pin_failed_attempts: i32,
    pub pin_locked_until: Option<crate::time::NaiveUtc>,
    #[sqlx(rename = "has_DVA")]
    pub has_dva: bool,
    pub nin_encrypted: Option<String>,
    pub bvn_encrypted: Option<String>,
    pub house_address: Option<String>,
    pub utility_bill_image: Option<String>,
    pub is_frozen: bool,
    pub frozen_reason: Option<String>,
}

#[derive(Debug, FromRow)]
pub struct EmailVerification {
    pub id: i64,
    pub email: String,
    pub otp: i32,
    pub timestamp: crate::time::NaiveUtc,
}

#[derive(Debug, FromRow)]
pub struct ResetPassword {
    pub id: i64,
    pub otp: i32,
    pub timestamp: crate::time::NaiveUtc,
    pub profile_id: i64,
}

#[derive(Debug, FromRow, Serialize, Clone)]
pub struct DvaAccount {
    pub id: i64,
    pub dedicated_account_id: Option<i32>,
    pub account_number: String,
    pub account_name: String,
    pub bank_name: String,
    pub bank_slug: String,
    pub bank_id: Option<i32>,
    pub customer_code: String,
    pub customer_id: Option<i32>,
    pub phone: Option<String>,
    pub bvn_encrypted: Option<String>,
    pub active: bool,
    pub paystack_response: Option<String>,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub user_id: i64,
    pub dva_account_name: Option<String>,
    pub dva_account_number: Option<String>,
}

const DVA_COLUMNS: &str = "id, dedicated_account_id, account_number, account_name, bank_name, bank_slug, bank_id, customer_code, customer_id, phone, bvn_encrypted, active, CAST(paystack_response AS TEXT) AS paystack_response, created_at, updated_at, user_id, dva_account_name, dva_account_number";

pub async fn find_dva_by_user(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {DVA_COLUMNS} FROM accounts_paystackdedicatedaccount WHERE user_id = $1"
    ))
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn find_dva_by_user_email(
    db: &sqlx::PgPool,
    email: &str,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    let cols = DVA_COLUMNS
        .split(", ")
        .map(|c| format!("d.{c}"))
        .collect::<Vec<_>>()
        .join(", ");
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {cols} FROM accounts_paystackdedicatedaccount d
         JOIN accounts_profile p ON p.id = d.user_id WHERE p.email = $1",
    ))
    .bind(email)
    .fetch_optional(db)
    .await
}

pub async fn find_dva_by_customer_code(
    db: &sqlx::PgPool,
    customer_code: &str,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {DVA_COLUMNS} FROM accounts_paystackdedicatedaccount WHERE customer_code = $1"
    ))
    .bind(customer_code)
    .fetch_optional(db)
    .await
}

pub async fn find_dva_by_account_number(
    db: &sqlx::PgPool,
    account_number: &str,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {DVA_COLUMNS} FROM accounts_paystackdedicatedaccount WHERE dva_account_number = $1"
    ))
    .bind(account_number)
    .fetch_optional(db)
    .await
}

pub async fn mark_dva_assigned(
    db: &sqlx::PgPool,
    id: i64,
    active: bool,
    payload_json: &str,
    dva_account_number: Option<&str>,
    dva_account_name: Option<&str>,
    customer_code: &str,
    dedicated_account_id: Option<i64>,
    customer_id: Option<i64>,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE accounts_paystackdedicatedaccount SET active = $1, paystack_response = $2, dva_account_number = $3,
         dva_account_name = $4, customer_code = $5, dedicated_account_id = $6, customer_id = $7, updated_at = $8 WHERE id = $9",
    )
    .bind(active)
    .bind(payload_json)
    .bind(dva_account_number)
    .bind(dva_account_name)
    .bind(customer_code)
    .bind(dedicated_account_id)
    .bind(customer_id)
    .bind(crate::time::Ts(&now))
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn set_has_dva(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE accounts_profile SET \"has_DVA\" = TRUE WHERE id = $1 AND \"has_DVA\" = FALSE")
        .bind(user_id)
        .execute(db)
        .await?;
    Ok(())
}

// ---------- Nomba dedicated accounts (accounts_nombadedicatedaccount) ----------

#[derive(Debug, FromRow, Serialize, Clone)]
pub struct NombaDvaAccount {
    pub id: i64,
    pub account_ref: String,
    pub account_number: String,
    pub account_name: String,
    pub bank_name: String,
    pub active: bool,
    pub nomba_response: Option<String>,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub user_id: i64,
}

const NOMBA_DVA_COLUMNS: &str = "id, account_ref, account_number, account_name, bank_name, active, CAST(nomba_response AS TEXT) AS nomba_response, created_at, updated_at, user_id";

pub async fn find_nomba_dva_by_user(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<NombaDvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, NombaDvaAccount>(&format!(
        "SELECT {NOMBA_DVA_COLUMNS} FROM accounts_nombadedicatedaccount WHERE user_id = $1"
    ))
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn find_active_nomba_dva_by_number(
    db: &sqlx::PgPool,
    account_number: &str,
) -> Result<Option<NombaDvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, NombaDvaAccount>(&format!(
        "SELECT {NOMBA_DVA_COLUMNS} FROM accounts_nombadedicatedaccount WHERE account_number = $1 AND active = TRUE"
    ))
    .bind(account_number)
    .fetch_optional(db)
    .await
}

pub async fn create_nomba_dva(
    db: &sqlx::PgPool,
    user_id: i64,
    account_ref: &str,
    account_number: &str,
    account_name: &str,
    bank_name: &str,
    active: bool,
    nomba_response_json: &str,
    now: &str,
) -> Result<NombaDvaAccount, sqlx::Error> {
    sqlx::query_as::<_, NombaDvaAccount>(&format!(
        "INSERT INTO accounts_nombadedicatedaccount
         (user_id, account_ref, account_number, account_name, bank_name, active, nomba_response, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, CAST($7 AS JSONB), $8, $8) RETURNING {NOMBA_DVA_COLUMNS}",
        NOMBA_DVA_COLUMNS = NOMBA_DVA_COLUMNS,
    ))
    .bind(user_id)
    .bind(account_ref)
    .bind(account_number)
    .bind(account_name)
    .bind(bank_name)
    .bind(active)
    .bind(nomba_response_json)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await
}
