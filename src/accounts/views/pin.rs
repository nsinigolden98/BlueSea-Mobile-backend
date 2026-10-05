//! Transaction-PIN HTTP handlers.
//! Lockout enforcement lives in `super::super::pin_security`
//! (mirrors `pin_security.py`); this file only handles request/response.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use chrono::Utc;
use rand::Rng;
use serde_json::json;

use crate::accounts::crypto as pin_crypto;
use crate::accounts::pin_security::verify_pin_with_lockout;
use crate::accounts::serializers::{
    ChangePinBody, NewPinBody, OtpOnlyBody, SetPinBody, VerifyPinBody,
};
use crate::accounts::utils::{pin_store, send_email_verification};
use crate::auth::extractor::auth_user;
use crate::auth::password as auth_password;
use crate::error::AppError;
use crate::state::AppState;

fn lockout_response(retry_after: i64) -> AppError {
    AppError {
        status: StatusCode::TOO_MANY_REQUESTS,
        message: format!(
            "Too many attempts. Try again in {} minutes.",
            retry_after / 60 + 1
        ),
    }
}

fn limits(s: &AppState) -> (i64, i64) {
    (
        s.config.pin_max_attempts as i64,
        s.config.pin_lockout_minutes,
    )
}

pub async fn pin_set(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<SetPinBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    let plain = pin_crypto::decrypt_pin(&b.pin, &s.config.pin_rsa_private_key_b64)
        .and_then(|p| {
            pin_crypto::decrypt_pin(&b.confirm_pin, &s.config.pin_rsa_private_key_b64)
                .map(|c| (p, c))
        })
        .map_err(|_| AppError::bad_request("Invalid transaction pin format"))?;
    if plain.0.len() != 4 || !plain.0.chars().all(|c| c.is_ascii_digit()) {
        return Err(AppError::bad_request("Pin must be a 4-digit number"));
    }
    if plain.0 != plain.1 {
        return Err(AppError::bad_request("Pin and confirm pin do not match"));
    }
    if user.pin_is_set {
        return Err(AppError::bad_request("Transaction pin is already set"));
    }
    let hashed = auth_password::hash_password(&plain.0);
    sqlx::query("UPDATE accounts_profile SET transaction_pin = ?, pin_is_set = 1, pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?")
        .bind(&hashed).bind(user.id).execute(&s.db).await?;
    Ok(Json(json!({"message": "Transaction pin set successfully", "state": true})))
}

pub async fn pin_verify(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<VerifyPinBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    if !user.pin_is_set {
        return Err(AppError::bad_request("Transaction pin is not set"));
    }
    let (max_attempts, lockout_minutes) = limits(&s);
    let r = verify_pin_with_lockout(
        &s.db,
        user.id,
        &b.pin,
        &s.config.pin_rsa_private_key_b64,
        max_attempts,
        lockout_minutes,
    )
    .await?;
    if r.locked {
        return Err(lockout_response(r.retry_after));
    }
    if r.ok {
        return Ok(Json(
            json!({"message": "Transaction pin verified successfully", "state": true}),
        ));
    }
    Err(AppError::bad_request("Invalid transaction pin"))
}

pub async fn pin_change(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<ChangePinBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    if !user.pin_is_set {
        return Err(AppError::bad_request("Transaction pin is not set"));
    }
    let (max_attempts, lockout_minutes) = limits(&s);
    let r = verify_pin_with_lockout(
        &s.db,
        user.id,
        &b.old_pin,
        &s.config.pin_rsa_private_key_b64,
        max_attempts,
        lockout_minutes,
    )
    .await?;
    if r.locked {
        return Err(lockout_response(r.retry_after));
    }
    if !r.ok {
        return Err(AppError::bad_request("Old pin is incorrect"));
    }
    let (plain_new, plain_confirm) =
        pin_crypto::decrypt_pin(&b.new_pin, &s.config.pin_rsa_private_key_b64)
            .and_then(|p| {
                pin_crypto::decrypt_pin(&b.confirm_pin, &s.config.pin_rsa_private_key_b64)
                    .map(|c| (p, c))
            })
            .map_err(|_| AppError::bad_request("Invalid transaction pin format"))?;
    if plain_new.len() != 4 || !plain_new.chars().all(|c| c.is_ascii_digit()) {
        return Err(AppError::bad_request("New pin must be a 4-digit number"));
    }
    if plain_new != plain_confirm {
        return Err(AppError::bad_request("New PINs do not match"));
    }
    let hashed = auth_password::hash_password(&plain_new);
    sqlx::query("UPDATE accounts_profile SET transaction_pin = ?, pin_is_set = 1, pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?")
        .bind(&hashed).bind(user.id).execute(&s.db).await?;
    Ok(Json(
        json!({"message": "Transaction pin changed successfully", "state": true}),
    ))
}

pub async fn pin_reset_request(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    if !user.pin_is_set {
        return Err(AppError::bad_request("Transaction PIN is not set"));
    }
    let otp = format!("{:06}", rand::thread_rng().gen_range(100000..=999999));
    {
        let mut store = pin_store().lock().unwrap();
        store
            .otps
            .insert(user.email.clone(), (otp.clone(), Utc::now().timestamp() + 600));
    }
    send_email_verification(
        &user.email,
        "Transaction Pin Reset Verification Code",
        &otp,
        s.config.debug,
    );
    Ok(Json(
        json!({"message": "Transaction Pin reset OTP sent to your email", "state": true}),
    ))
}

pub async fn pin_reset_verify_otp(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<OtpOnlyBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    let cached = {
        let store = pin_store().lock().unwrap();
        store.otps.get(&user.email).cloned()
    };
    let Some((code, exp)) = cached else {
        return Err(AppError::bad_request("OTP has expired or is invalid"));
    };
    if Utc::now().timestamp() > exp {
        pin_store().lock().unwrap().otps.remove(&user.email);
        return Err(AppError::bad_request("OTP has expired or is invalid"));
    }
    if code != b.otp {
        return Err(AppError::bad_request("Invalid OTP"));
    }
    let token = uuid::Uuid::new_v4().to_string();
    {
        let mut store = pin_store().lock().unwrap();
        store.otps.remove(&user.email);
        store.tokens.insert(
            user.email.clone(),
            (token.clone(), Utc::now().timestamp() + 300),
        );
    }
    Ok(Json(json!({"message": "OTP verified successfully", "state": true, "verification_token": token})))
}

pub async fn pin_reset_new(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<NewPinBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    let cached = {
        pin_store()
            .lock()
            .unwrap()
            .tokens
            .get(&user.email)
            .cloned()
    };
    let Some((tok, exp)) = cached else {
        return Err(AppError::bad_request(
            "Invalid or expired verification token",
        ));
    };
    if tok != b.verification_token || Utc::now().timestamp() > exp {
        return Err(AppError::bad_request(
            "Invalid or expired verification token",
        ));
    }
    let (plain_new, plain_confirm) =
        pin_crypto::decrypt_pin(&b.new_pin, &s.config.pin_rsa_private_key_b64)
            .and_then(|p| {
                pin_crypto::decrypt_pin(&b.confirm_pin, &s.config.pin_rsa_private_key_b64)
                    .map(|c| (p, c))
            })
            .map_err(|_| AppError::bad_request("Invalid transaction pin format"))?;
    if plain_new.len() != 4 || !plain_new.chars().all(|c| c.is_ascii_digit()) {
        return Err(AppError::bad_request("PIN must be a 4-digit number"));
    }
    if plain_new != plain_confirm {
        return Err(AppError::bad_request("PINs do not match"));
    }
    let hashed = auth_password::hash_password(&plain_new);
    sqlx::query("UPDATE accounts_profile SET transaction_pin = ?, pin_is_set = 1, pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?")
        .bind(&hashed).bind(user.id).execute(&s.db).await?;
    pin_store().lock().unwrap().tokens.remove(&user.email);
    Ok(Json(
        json!({"message": "Transaction PIN reset successfully", "state": true}),
    ))
}
