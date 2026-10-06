//! Database row types for the accounts app.
//! Mirrors `accounts/models.py` — table shapes only, no request/response DTOs
//! (those live in `serializers.rs`, like DRF serializers).

use serde::Serialize;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow, Serialize)]
pub struct Profile {
    pub id: i64,
    pub password: String,
    pub last_login: Option<chrono::NaiveDateTime>,
    pub is_superuser: bool,
    pub first_name: String,
    pub last_name: String,
    pub date_joined: chrono::NaiveDateTime,
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
    pub created_on: chrono::NaiveDateTime,
    pub pin_is_set: bool,
    pub transaction_pin: Option<String>,
    pub referral_code: String,
    pub pin_failed_attempts: i64,
    pub pin_locked_until: Option<chrono::NaiveDateTime>,
    #[sqlx(rename = "has_DVA")]
    pub has_dva: bool,
}

#[derive(Debug, FromRow)]
pub struct EmailVerification {
    pub id: i64,
    pub email: String,
    pub otp: i64,
    pub timestamp: chrono::NaiveDateTime,
}

#[derive(Debug, FromRow)]
pub struct ResetPassword {
    pub id: i64,
    pub otp: i64,
    pub timestamp: chrono::NaiveDateTime,
    pub profile_id: i64,
}

#[derive(Debug, FromRow, Serialize, Clone)]
pub struct DvaAccount {
    pub id: i64,
    pub dedicated_account_id: Option<i64>,
    pub account_number: String,
    pub account_name: String,
    pub bank_name: String,
    pub bank_slug: String,
    pub bank_id: Option<i64>,
    pub customer_code: String,
    pub customer_id: Option<i64>,
    pub phone: Option<String>,
    pub bvn_encrypted: Option<String>,
    pub active: bool,
    pub paystack_response: Option<String>,
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
    pub user_id: i64,
    pub dva_account_name: Option<String>,
    pub dva_account_number: Option<String>,
}

const DVA_COLUMNS: &str = "id, dedicated_account_id, account_number, account_name, bank_name, bank_slug, bank_id, customer_code, customer_id, phone, bvn_encrypted, active, paystack_response, created_at, updated_at, user_id, dva_account_name, dva_account_number";

pub async fn find_dva_by_user(
    db: &sqlx::SqlitePool,
    user_id: i64,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {DVA_COLUMNS} FROM accounts_paystackdedicatedaccount WHERE user_id = ?"
    ))
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn find_dva_by_user_email(
    db: &sqlx::SqlitePool,
    email: &str,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    let cols = DVA_COLUMNS
        .split(", ")
        .map(|c| format!("d.{c}"))
        .collect::<Vec<_>>()
        .join(", ");
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {cols} FROM accounts_paystackdedicatedaccount d
         JOIN accounts_profile p ON p.id = d.user_id WHERE p.email = ?",
    ))
    .bind(email)
    .fetch_optional(db)
    .await
}

pub async fn find_dva_by_customer_code(
    db: &sqlx::SqlitePool,
    customer_code: &str,
) -> Result<Option<DvaAccount>, sqlx::Error> {
    sqlx::query_as::<_, DvaAccount>(&format!(
        "SELECT {DVA_COLUMNS} FROM accounts_paystackdedicatedaccount WHERE customer_code = ?"
    ))
    .bind(customer_code)
    .fetch_optional(db)
    .await
}

pub async fn mark_dva_assigned(
    db: &sqlx::SqlitePool,
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
        "UPDATE accounts_paystackdedicatedaccount SET active = ?, paystack_response = ?, dva_account_number = ?,
         dva_account_name = ?, customer_code = ?, dedicated_account_id = ?, customer_id = ?, updated_at = ? WHERE id = ?",
    )
    .bind(active)
    .bind(payload_json)
    .bind(dva_account_number)
    .bind(dva_account_name)
    .bind(customer_code)
    .bind(dedicated_account_id)
    .bind(customer_id)
    .bind(now)
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn set_has_dva(
    db: &sqlx::SqlitePool,
    user_id: i64,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE accounts_profile SET has_DVA = 1 WHERE id = ? AND has_DVA = 0")
        .bind(user_id)
        .execute(db)
        .await?;
    Ok(())
}
