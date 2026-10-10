//! Signup / login / email verification / password reset.
//! Mirrors `accounts/views.py` auth section + `serializers.py` shapes.

use axum::{Json, extract::State, http::StatusCode};
use chrono::Utc;
use serde_json::json;

use crate::accounts::models::{EmailVerification, Profile, ResetPassword};
use crate::accounts::serializers::{
    EmailOnlyBody, LoginBody, LogoutBody, OtpBody, ProfilePublic, ResetConfirmBody,
    SignUpBody,
};
use crate::accounts::utils::{
    now_naive, password_reset_email, password_reset_success_email, referral_code,
    reset_token, send_rendered_email, signup_verification_email, six_digit_otp,
};
use crate::auth::extractor::get_profile;
use crate::auth::{jwt as auth_jwt, password as auth_password};
use crate::error::AppError;
use crate::state::AppState;

#[utoipa::path(
    post,
    path = "/accounts/sign-up/",
    tag = "Authentication",
    summary = "Register a new user",
    description = "Create a new user account and send email verification",
    request_body = SignUpBody,
    responses(
        (status = 201, description = "Account created, verification email sent"),
        (status = 400, description = "Registration failed"),
        (status = 500, description = "Verification email failed"),
    ),
)]
pub async fn sign_up(
    State(s): State<AppState>,
    Json(b): Json<SignUpBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    if b.surname.trim().is_empty()
        || b.other_names.trim().is_empty()
        || b.phone.trim().is_empty()
        || b.password.is_empty()
    {
        return Err(AppError::bad_request("Registration Failed"));
    }
    if !b.email.contains('@') {
        return Err(AppError::bad_request("Registration Failed"));
    }
    let exists: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM accounts_profile WHERE email = $1")
            .bind(&b.email)
            .fetch_optional(&s.db)
            .await?;
    if exists.is_some() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"message": "Registration Failed", "errors": {"email": ["Email already exists."]}, "state": false})),
        ));
    }
    let now = now_naive().to_string();
    let pw = auth_password::hash_password(&b.password);
    let ref_code = loop {
        let c: String = referral_code();
        let hit: Option<(i64,)> =
            sqlx::query_as("SELECT id FROM accounts_profile WHERE referral_code = $1")
                .bind(&c)
                .fetch_optional(&s.db)
                .await?;
        if hit.is_none() {
            break c;
        }
    };
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO accounts_profile (password, last_login, is_superuser, first_name, last_name, date_joined, email, surname, other_names, phone, image, verification_code, is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, transaction_pin, referral_code, pin_failed_attempts, pin_locked_until, \"has_DVA\")
         VALUES ($1, NULL, FALSE, '', '', $2, $3, $4, $5, $6, NULL, NULL, TRUE, FALSE, FALSE, 'user', FALSE, $7, FALSE, NULL, $8, 0, NULL, FALSE) RETURNING id")
        .bind(&pw).bind(crate::time::Ts(&now)).bind(&b.email).bind(&b.surname).bind(&b.other_names).bind(&b.phone).bind(crate::time::Ts(&now)).bind(&ref_code)
        .fetch_one(&s.db).await?;
    let user_id = res.0;
    sqlx::query("INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id) VALUES ('0.00', '0.00', $1, $2, TRUE, $3)")
        .bind(crate::time::Ts(&now)).bind(crate::time::Ts(&now)).bind(user_id).execute(&s.db).await?;
    // Mirrors the post_save signal: every user gets a bonus account.
    let _ = crate::bonus::models::ensure_point(&s.db, user_id, &now).await;

    let otp = six_digit_otp();
    let rendered = signup_verification_email(&s.config.site_url, &b.email, &otp);
    send_rendered_email(&s, &rendered).await;
    sqlx::query("INSERT INTO accounts_emailverification (email, otp, timestamp) VALUES ($1, $2, $3) ON CONFLICT (email) DO UPDATE SET otp=excluded.otp, timestamp=excluded.timestamp")
        .bind(&b.email).bind(otp.parse::<i64>().unwrap_or(0)).bind(crate::time::Ts(&now)).execute(&s.db).await?;

    Ok((
        StatusCode::CREATED,
        Json(json!({"message": "Account successfully created, check your email", "state": true})),
    ))
}

#[utoipa::path(
    post,
    path = "/accounts/verify-email/",
    tag = "Authentication",
    summary = "Verify email address",
    description = "Verify user's email using the OTP sent to their email (10 minute window)",
    request_body = OtpBody,
    responses(
        (status = 200, description = "Email verified, JWT pair returned"),
        (status = 400, description = "Invalid or expired OTP"),
    ),
)]
pub async fn verify_email(
    State(s): State<AppState>,
    Json(b): Json<OtpBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let rec: Option<EmailVerification> =
        sqlx::query_as("SELECT * FROM accounts_emailverification WHERE email = $1")
            .bind(&b.email)
            .fetch_optional(&s.db)
            .await?;
    let rec = rec.ok_or_else(|| AppError::bad_request("Email not found"))?;
    let otp_int: i32 = b
        .otp
        .parse()
        .map_err(|_| AppError::bad_request("Invalid OTP"))?;
    if rec.timestamp.and_utc().timestamp() + 600 < Utc::now().timestamp() {
        sqlx::query("DELETE FROM accounts_emailverification WHERE email = $1")
            .bind(&b.email)
            .execute(&s.db)
            .await?;
        return Err(AppError::bad_request("OTP has expired"));
    }
    if rec.otp != otp_int {
        return Err(AppError::bad_request("Invalid OTP"));
    }
    let user: Option<Profile> =
        sqlx::query_as("SELECT * FROM accounts_profile WHERE email = $1")
            .bind(&rec.email)
            .fetch_optional(&s.db)
            .await?;
    let user = user.ok_or_else(|| AppError::bad_request("User not found"))?;
    sqlx::query("UPDATE accounts_profile SET email_verified = TRUE WHERE id = $1")
        .bind(user.id)
        .execute(&s.db)
        .await?;
    sqlx::query("DELETE FROM accounts_emailverification WHERE email = $1")
        .bind(&b.email)
        .execute(&s.db)
        .await?;
    let (access, refresh) =
        auth_jwt::create_token_pair(user.id, &user.role, &s.config.secret_key)
            .map_err(|e| AppError::internal(e.to_string()))?;
    let rc = auth_jwt::decode_claims(&refresh, &s.config.secret_key).unwrap();
    auth_jwt::record_outstanding(&s.db, user.id, &rc.jti, &refresh, rc.exp).await?;
    Ok(Json(
        json!({"message": "Email verified successfully", "state": true, "refresh_token": refresh, "access_token": access}),
    ))
}

#[utoipa::path(
    post,
    path = "/accounts/resend-otp/",
    tag = "Authentication",
    summary = "Resend OTP",
    description = "Resend verification OTP to user's email",
    request_body = EmailOnlyBody,
    responses(
        (status = 201, description = "OTP sent"),
        (status = 400, description = "Email does not exist"),
        (status = 500, description = "Email send failed"),
    ),
)]
pub async fn resend_otp(
    State(s): State<AppState>,
    Json(b): Json<EmailOnlyBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let exists: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM accounts_profile WHERE email = $1")
            .bind(&b.email)
            .fetch_optional(&s.db)
            .await?;
    if exists.is_none() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"message": "Email does not exist", "state": false})),
        ));
    }
    sqlx::query("DELETE FROM accounts_emailverification WHERE email = $1")
        .bind(&b.email)
        .execute(&s.db)
        .await?;
    let otp = six_digit_otp();
    let now = now_naive().to_string();
    let rendered = signup_verification_email(&s.config.site_url, &b.email, &otp);
    send_rendered_email(&s, &rendered).await;
    sqlx::query("INSERT INTO accounts_emailverification (email, otp, timestamp) VALUES ($1, $2, $3) ON CONFLICT (email) DO UPDATE SET otp=excluded.otp, timestamp=excluded.timestamp")
        .bind(&b.email).bind(otp.parse::<i64>().unwrap_or(0)).bind(crate::time::Ts(&now)).execute(&s.db).await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({"message": "Otp successfully sent, check your email", "state": true})),
    ))
}

#[utoipa::path(
    post,
    path = "/accounts/login/",
    tag = "Authentication",
    summary = "User login",
    description = "Authenticate user and return JWT tokens",
    request_body = LoginBody,
    responses(
        (status = 200, description = "Login successful"),
        (status = 401, description = "Invalid credentials"),
    ),
)]
pub async fn login(
    State(s): State<AppState>,
    Json(b): Json<LoginBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user: Option<Profile> =
        sqlx::query_as("SELECT * FROM accounts_profile WHERE email = $1")
            .bind(&b.email)
            .fetch_optional(&s.db)
            .await?;
    let user = user.ok_or_else(|| {
        AppError::unauthorized("No active account found with the given credentials")
    })?;
    if !user.is_active || !auth_password::verify_password(&b.password, &user.password) {
        return Err(AppError::unauthorized(
            "No active account found with the given credentials",
        ));
    }
    let now = now_naive().to_string();
    sqlx::query("UPDATE accounts_profile SET last_login = $1 WHERE id = $2")
        .bind(crate::time::Ts(&now))
        .bind(user.id)
        .execute(&s.db)
        .await?;
    let (access, refresh) =
        auth_jwt::create_token_pair(user.id, &user.role, &s.config.secret_key)
            .map_err(|e| AppError::internal(e.to_string()))?;
    let rc = auth_jwt::decode_claims(&refresh, &s.config.secret_key).unwrap();
    auth_jwt::record_outstanding(&s.db, user.id, &rc.jti, &refresh, rc.exp).await?;
    Ok(Json(
        json!({"access_token": access, "refresh_token": refresh, "user": ProfilePublic::from(&user)}),
    ))
}

#[utoipa::path(
    post,
    path = "/accounts/logout/",
    tag = "Authentication",
    summary = "User logout",
    description = "Logout user by blacklisting their refresh token",
    request_body = LogoutBody,
    responses(
        (status = 200, description = "Logout successful"),
        (status = 400, description = "Invalid token"),
    ),
    security(("bearer" = [])),
)]
pub async fn logout(
    State(s): State<AppState>,
    Json(b): Json<LogoutBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let claims = auth_jwt::decode_claims(&b.refresh_token, &s.config.secret_key)
        .map_err(|_| AppError::bad_request("Invalid token or logout failed"))?;
    if !auth_jwt::blacklist_jti(&s.db, &claims.jti).await? {
        let row: Option<(String,)> =
            sqlx::query_as("SELECT jti FROM token_blacklist_outstandingtoken WHERE token = $1")
                .bind(&b.refresh_token)
                .fetch_optional(&s.db)
                .await?;
        if let Some((jti,)) = row {
            auth_jwt::blacklist_jti(&s.db, &jti).await?;
        } else {
            return Err(AppError::bad_request("Invalid token or logout failed"));
        }
    }
    Ok(Json(json!({"message": "Logout successful", "state": true})))
}

#[utoipa::path(
    post,
    path = "/accounts/password/reset/request/",
    tag = "Authentication",
    summary = "Request password reset",
    description = "Send OTP to user's email for password reset",
    request_body = EmailOnlyBody,
    responses(
        (status = 200, description = "Reset OTP sent (or generic success)"),
        (status = 500, description = "Email send failed"),
    ),
)]
pub async fn password_reset_request(
    State(s): State<AppState>,
    Json(b): Json<EmailOnlyBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user: Option<Profile> =
        sqlx::query_as("SELECT * FROM accounts_profile WHERE email = $1")
            .bind(&b.email)
            .fetch_optional(&s.db)
            .await?;
    let Some(user) = user else {
        return Ok(Json(
            json!({"message": "If an account exists with this email, you will receive a reset code", "state": true}),
        ));
    };
    let otp = six_digit_otp();
    let now = now_naive().to_string();
    let existing: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM accounts_resetpassword WHERE profile_id = $1")
            .bind(user.id)
            .fetch_optional(&s.db)
            .await?;
    if existing.is_some() {
        sqlx::query("UPDATE accounts_resetpassword SET otp = $1, timestamp = $2 WHERE profile_id = $3")
            .bind(otp.parse::<i64>().unwrap_or(0)).bind(crate::time::Ts(&now)).bind(user.id).execute(&s.db).await?;
    } else {
        sqlx::query("INSERT INTO accounts_resetpassword (otp, timestamp, profile_id) VALUES ($1, $2, $3)")
            .bind(otp.parse::<i64>().unwrap_or(0)).bind(crate::time::Ts(&now)).bind(user.id).execute(&s.db).await?;
    }
    let rendered = password_reset_email(&s.config.site_url, &user.email, &otp);
    send_rendered_email(&s, &rendered).await;
    Ok(Json(
        json!({"message": "Password reset OTP sent to your email", "state": true}),
    ))
}

#[utoipa::path(
    post,
    path = "/accounts/password/reset/verify-otp/",
    tag = "Authentication",
    summary = "Verify password reset OTP",
    description = "Verify the OTP and return a single-use token for password reset",
    request_body = OtpBody,
    responses(
        (status = 200, description = "OTP verified, reset token returned"),
        (status = 400, description = "Invalid or expired OTP"),
    ),
)]
pub async fn password_reset_verify_otp(
    State(s): State<AppState>,
    Json(b): Json<OtpBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let rec: Option<ResetPassword> = sqlx::query_as(
        "SELECT r.* FROM accounts_resetpassword r JOIN accounts_profile p ON p.id = r.profile_id WHERE p.email = $1")
        .bind(&b.email)
        .fetch_optional(&s.db)
        .await?;
    let Some(rec) = rec else {
        return Err(AppError::bad_request("Invalid request"));
    };
    if rec.timestamp.and_utc().timestamp() + 600 < Utc::now().timestamp() {
        sqlx::query("DELETE FROM accounts_resetpassword WHERE id = $1")
            .bind(rec.id)
            .execute(&s.db)
            .await?;
        return Err(AppError::bad_request("OTP has expired"));
    }
    let otp_int: i32 = b
        .otp
        .parse()
        .map_err(|_| AppError::bad_request("Invalid OTP"))?;
    if rec.otp != otp_int {
        return Err(AppError::bad_request("Invalid OTP"));
    }
    let token = reset_token::issue(&s.config.secret_key, &b.email);
    let now = now_naive().to_string();
    sqlx::query(
        "INSERT INTO accounts_resetpasswordvaluationtoken (reset_token, created_on) VALUES ($1, $2)",
    )
    .bind(&token)
    .bind(crate::time::Ts(&now))
    .execute(&s.db)
    .await?;
    sqlx::query("DELETE FROM accounts_resetpassword WHERE id = $1")
        .bind(rec.id)
        .execute(&s.db)
        .await?;
    Ok(Json(
        json!({"message": "OTP verified successfully", "state": true, "reset_token": token}),
    ))
}

#[utoipa::path(
    post,
    path = "/accounts/password/reset/confirm/",
    tag = "Authentication",
    summary = "Reset password",
    description = "Reset user password using the verified token (single use, 15 minute window)",
    request_body = ResetConfirmBody,
    responses(
        (status = 200, description = "Password reset successfully"),
        (status = 400, description = "Invalid token or weak password"),
    ),
)]
pub async fn password_reset_confirm(
    State(s): State<AppState>,
    Json(b): Json<ResetConfirmBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    if b.new_password != b.confirm_password {
        return Err(AppError::bad_request(
            "New password and confirm password do not match",
        ));
    }
    if b.new_password.len() < 8 {
        return Err(AppError::bad_request(
            "Password must be at least 8 characters long",
        ));
    }
    let email =
        reset_token::verify(&s.config.secret_key, &b.token, 900).map_err(AppError::bad_request)?;
    let tok: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM accounts_resetpasswordvaluationtoken WHERE reset_token = $1",
    )
    .bind(&b.token)
    .fetch_optional(&s.db)
    .await?;
    if tok.is_none() {
        return Err(AppError::bad_request(
            "Invalid or already used reset token",
        ));
    }
    let user: Option<Profile> =
        sqlx::query_as("SELECT * FROM accounts_profile WHERE email = $1")
            .bind(&email)
            .fetch_optional(&s.db)
            .await?;
    let Some(user) = user else {
        return Err(AppError::bad_request("User not found"));
    };
    let pw = auth_password::hash_password(&b.new_password);
    sqlx::query("UPDATE accounts_profile SET password = $1 WHERE id = $2")
        .bind(&pw)
        .bind(user.id)
        .execute(&s.db)
        .await?;
    sqlx::query("DELETE FROM accounts_resetpasswordvaluationtoken WHERE reset_token = $1")
        .bind(&b.token)
        .execute(&s.db)
        .await?;
    sqlx::query("DELETE FROM accounts_resetpassword WHERE profile_id = $1")
        .bind(user.id)
        .execute(&s.db)
        .await?;
    let _ = get_profile(&s.db, user.id).await?;
    send_rendered_email(
        &s,
        &password_reset_success_email(&s.config.site_url, &user.email),
    )
    .await;
    Ok(Json(json!({"message": "Password reset successfully", "state": true})))
}
