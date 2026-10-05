//! Social-login HTTP handlers. Provider verification lives in
//! `super::super::social_auth` (mirrors `social_auth.py`); this file only
//! handles the request/response layer.

use axum::{Json, extract::State};
use serde_json::json;

use crate::accounts::serializers::{AppleLoginBody, GoogleLoginBody, ProfilePublic};
use crate::accounts::social_auth::{AppleAuth, GoogleAuth, get_or_create_social_user};
use crate::auth::jwt as auth_jwt;
use crate::error::AppError;
use crate::state::AppState;

#[utoipa::path(
    post,
    path = "/accounts/auth/google/",
    tag = "Authentication",
    summary = "Google OAuth login",
    description = "Authenticate using Google ID token (client-side) or authorization code (server-side) flow",
    request_body = GoogleLoginBody,
    responses(
        (status = 200, description = "Login successful"),
        (status = 400, description = "Invalid request"),
        (status = 401, description = "Google authentication failed"),
    ),
)]
pub async fn google_login(
    State(s): State<AppState>,
    Json(b): Json<GoogleLoginBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let social = if let Some(id_token) = b.id_token.filter(|t| !t.is_empty()) {
        GoogleAuth::verify_google_token(&s.http, &id_token, &s.config.google_client_id)
            .await
            .map_err(|e| AppError::unauthorized(format!("Google authentication failed: {e}")))?
    } else if let Some(code) = b.authorization_code.filter(|c| !c.is_empty()) {
        GoogleAuth::exchange_code_for_token(
            &s.http,
            &s.config.google_client_id,
            &s.config.google_client_secret,
            &code,
            &b.redirect_uri.unwrap_or_default(),
        )
        .await
        .map_err(AppError::unauthorized)?
    } else {
        return Err(AppError::bad_request(
            "No authentication credentials provided",
        ));
    };

    let (user, is_new) =
        get_or_create_social_user(&s.db, "google", &social, None, b.phone.as_deref())
            .await?;
    let (access, refresh) =
        auth_jwt::create_token_pair(user.id, &user.role, &s.config.secret_key)
            .map_err(|e| AppError::internal(e.to_string()))?;
    let rc = auth_jwt::decode_claims(&refresh, &s.config.secret_key).unwrap();
    auth_jwt::record_outstanding(&s.db, user.id, &rc.jti, &refresh, rc.exp).await?;
    Ok(Json(json!({
        "success": true,
        "message": if is_new { "Account created successfully" } else { "Login successful" },
        "access_token": access, "refresh_token": refresh,
        "user": ProfilePublic::from(&user), "is_new_user": is_new,
    })))
}

#[utoipa::path(
    post,
    path = "/accounts/auth/apple/",
    tag = "Authentication",
    summary = "Apple OAuth login",
    description = "Authenticate user using Apple identity token",
    request_body = AppleLoginBody,
    responses(
        (status = 200, description = "Login successful"),
        (status = 400, description = "Invalid request"),
        (status = 401, description = "Apple authentication failed"),
    ),
)]
pub async fn apple_login(
    State(s): State<AppState>,
    Json(b): Json<AppleLoginBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let social = AppleAuth::verify_apple_token(&s.http, &s.config.apple_client_id, &b.id_token)
        .await
        .map_err(|e| AppError::unauthorized(format!("Apple authentication failed: {e}")))?;

    let mut phone = b.phone.clone();
    if phone.is_none() {
        phone = b
            .user
            .as_ref()
            .and_then(|u| u.get("phone"))
            .and_then(|v| v.as_str())
            .map(|x| x.to_string());
    }
    let (user, is_new) =
        get_or_create_social_user(&s.db, "apple", &social, b.user.as_ref(), phone.as_deref())
            .await?;
    let (access, refresh) =
        auth_jwt::create_token_pair(user.id, &user.role, &s.config.secret_key)
            .map_err(|e| AppError::internal(e.to_string()))?;
    let rc = auth_jwt::decode_claims(&refresh, &s.config.secret_key).unwrap();
    auth_jwt::record_outstanding(&s.db, user.id, &rc.jti, &refresh, rc.exp).await?;
    Ok(Json(json!({
        "success": true,
        "message": if is_new { "Account created successfully" } else { "Login successful" },
        "access_token": access, "refresh_token": refresh,
        "user": ProfilePublic::from(&user), "is_new_user": is_new,
    })))
}
