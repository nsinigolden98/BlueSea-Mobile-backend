//! Admin models for `accounts`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "accounts.EmailVerification",
        label: "Email Verification",
        table: "accounts_emailverification",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("email", ColType::Text),
        ("otp", ColType::Int),
        ("timestamp", ColType::DateTime),
        ],
        search: &["email"],
        default_order: "-id",
    });
    out.push(ModelDef {
        name: "accounts.NombaDedicatedAccount",
        label: "Nomba Dedicated Account",
        table: "accounts_nombadedicatedaccount",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("account_ref", ColType::Text),
        ("account_number", ColType::Text),
        ("account_name", ColType::Text),
        ("bank_name", ColType::Text),
        ("active", ColType::Bool),
        ("nomba_response", ColType::Json),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ],
        search: &["account_name", "bank_name"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "accounts.PaystackDedicatedAccount",
        label: "Paystack Dedicated Account",
        table: "accounts_paystackdedicatedaccount",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("dedicated_account_id", ColType::Int),
        ("account_number", ColType::Text),
        ("account_name", ColType::Text),
        ("bank_name", ColType::Text),
        ("bank_slug", ColType::Text),
        ("bank_id", ColType::Int),
        ("customer_code", ColType::Text),
        ("customer_id", ColType::Int),
        ("phone", ColType::Text),
        ("bvn_encrypted", ColType::Text),
        ("active", ColType::Bool),
        ("paystack_response", ColType::Json),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ("dva_account_name", ColType::Text),
        ("dva_account_number", ColType::Text),
        ],
        search: &["account_name", "bank_name", "customer_code", "phone", "dva_account_name"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "accounts.Profile",
        label: "Profile",
        table: "accounts_profile",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("password", ColType::Text),
        ("last_login", ColType::DateTime),
        ("is_superuser", ColType::Bool),
        ("first_name", ColType::Text),
        ("last_name", ColType::Text),
        ("date_joined", ColType::DateTime),
        ("email", ColType::Text),
        ("surname", ColType::Text),
        ("other_names", ColType::Text),
        ("phone", ColType::Text),
        ("image", ColType::Text),
        ("verification_code", ColType::Text),
        ("is_active", ColType::Bool),
        ("is_staff", ColType::Bool),
        ("is_admin", ColType::Bool),
        ("role", ColType::Text),
        ("email_verified", ColType::Bool),
        ("created_on", ColType::DateTime),
        ("pin_is_set", ColType::Bool),
        ("transaction_pin", ColType::Text),
        ("referral_code", ColType::Text),
        ("pin_failed_attempts", ColType::Int),
        ("pin_locked_until", ColType::DateTime),
        ("has_DVA", ColType::Bool),
        ("nin_encrypted", ColType::Text),
        ("bvn_encrypted", ColType::Text),
        ("house_address", ColType::Text),
        ("utility_bill_image", ColType::Text),
        ("is_frozen", ColType::Bool),
        ("frozen_reason", ColType::Text),
        ],
        search: &["first_name", "last_name", "email", "surname", "other_names"],
        default_order: "-id",
    });
    out.push(ModelDef {
        name: "accounts.ResetPassword",
        label: "Reset Password",
        table: "accounts_resetpassword",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("otp", ColType::Int),
        ("timestamp", ColType::DateTime),
        ("profile_id", ColType::Int),
        ],
        search: &[],
        default_order: "-id",
    });
    out.push(ModelDef {
        name: "accounts.ResetPasswordValuationToken",
        label: "Reset Password Valuation Token",
        table: "accounts_resetpasswordvaluationtoken",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("reset_token", ColType::Text),
        ("created_on", ColType::DateTime),
        ],
        search: &[],
        default_order: "-id",
    });
}

/// Unfreeze a tier-frozen profile. Staff-only; nothing else can clear
/// `is_frozen` (no user-facing endpoint touches it).
pub async fn unfreeze_profile(
    axum::extract::State(s): axum::extract::State<crate::state::AppState>,
    headers: axum::http::HeaderMap,
    axum::extract::Path(id): axum::extract::Path<String>,
) -> super::Resp {
    use axum::http::StatusCode;
    let admin = match super::require_staff(&s, headers).await {
        Ok(u) => u,
        Err(e) => return e,
    };
    let uid: i64 = match id.trim().parse() {
        Ok(v) => v,
        Err(_) => return (StatusCode::NOT_FOUND, axum::Json(serde_json::json!({"detail": "Not found."}))),
    };
    let now = crate::time::now_str();
    let res = sqlx::query(
        "UPDATE accounts_profile SET is_frozen = FALSE, frozen_reason = NULL WHERE id = $1 AND is_frozen = TRUE",
    )
    .bind(uid)
    .execute(&s.db)
    .await;
    match res {
        Ok(r) if r.rows_affected() > 0 => {
            tracing::info!("admin {} unfroze profile {uid}", admin.id);
            (StatusCode::OK, axum::Json(serde_json::json!({"success": true, "unfrozen": uid})))
        }
        Ok(_) => (StatusCode::NOT_FOUND, axum::Json(serde_json::json!({"detail": "Not found or not frozen."}))),
        Err(e) => super::err_json(crate::error::AppError::internal(format!("Unfreeze failed: {e} – {now}"))),
    }
}
