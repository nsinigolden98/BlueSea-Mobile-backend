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
