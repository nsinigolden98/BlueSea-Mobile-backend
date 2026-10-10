//! Request/response shapes for the accounts app.
//! Mirrors `accounts/serializers.py` + `social_serializers.py`.

use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

use super::models::Profile;

#[derive(Debug, Serialize, ToSchema)]
pub struct ProfilePublic {
    pub id: i64,
    pub email: String,
    pub role: String,
    pub email_verified: bool,
    pub is_staff: bool,
    pub is_admin: bool,
    pub created_on: chrono::NaiveDateTime,
}

impl From<&Profile> for ProfilePublic {
    fn from(p: &Profile) -> Self {
        Self {
            id: p.id,
            email: p.email.clone(),
            role: p.role.clone(),
            email_verified: p.email_verified,
            is_staff: p.is_staff,
            is_admin: p.is_admin,
            created_on: p.created_on.0,
        }
    }
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct SignUpBody {
    pub surname: String,
    pub other_names: String,
    pub email: String,
    pub phone: String,
    pub password: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct OtpBody {
    pub email: String,
    pub otp: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct LoginBody {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct EmailOnlyBody {
    pub email: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct ResetConfirmBody {
    pub token: String,
    pub new_password: String,
    pub confirm_password: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct LogoutBody {
    pub refresh_token: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct SetPinBody {
    pub pin: String,
    pub confirm_pin: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct ChangePinBody {
    pub old_pin: String,
    pub new_pin: String,
    pub confirm_pin: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct VerifyPinBody {
    pub pin: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct OtpOnlyBody {
    pub otp: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct NewPinBody {
    pub verification_token: String,
    pub new_pin: String,
    pub confirm_pin: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct LookupBody {
    pub email: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct GoogleLoginBody {
    pub id_token: Option<String>,
    pub authorization_code: Option<String>,
    pub redirect_uri: Option<String>,
    pub phone: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct AppleLoginBody {
    pub id_token: String,
    pub phone: Option<String>,
    pub user: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct DvaAssignBody {
    pub first_name: String,
    pub last_name: String,
    pub account_number: String,
    pub bank_code: String,
    pub bvn: String,
    pub phone: Option<String>,
}
