use axum::extract::State;
use axum::http::HeaderMap;

use crate::auth::jwt as auth_jwt;
use crate::accounts::models::Profile;
use crate::error::AppError;
use crate::state::AppState;

pub async fn get_profile(db: &sqlx::SqlitePool, id: i64) -> Result<Profile, AppError> {
    sqlx::query_as::<_, Profile>("SELECT * FROM accounts_profile WHERE id = ?")
        .bind(id)
        .fetch_optional(db)
        .await?
        .ok_or_else(|| AppError::unauthorized("User not found"))
}

fn require_bearer(headers: &HeaderMap) -> Result<String, AppError> {
    let v = headers
        .get("authorization")
        .and_then(|h| h.to_str().ok())
        .ok_or_else(|| AppError::unauthorized("Authentication required"))?;
    v.strip_prefix("Bearer ")
        .map(|s| s.to_string())
        .ok_or_else(|| AppError::unauthorized("Authentication required"))
}

/// Authenticated-user extractor.
/// Mirrors DRF `IsAuthenticated` + `JWTAuthentication`.
pub async fn auth_user(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Profile, AppError> {
    let token = require_bearer(&headers)?;
    let claims = auth_jwt::decode_claims(&token, &s.config.secret_key)
        .map_err(|_| AppError::unauthorized("Invalid token"))?;
    if claims.token_type != "access" {
        return Err(AppError::unauthorized("Invalid token"));
    }
    if auth_jwt::is_blacklisted(&s.db, &claims.jti).await? {
        return Err(AppError::unauthorized("Token revoked"));
    }
    get_profile(&s.db, claims.user_id).await
}
