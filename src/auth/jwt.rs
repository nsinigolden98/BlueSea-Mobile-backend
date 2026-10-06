use chrono::{Duration, Utc};
use jsonwebtoken::{DecodingKey, EncodingKey, Header, Validation, decode, encode};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Claims {
    pub token_type: String, // "access" | "refresh"
    pub exp: i64,
    pub iat: i64,
    pub jti: String,
    pub user_id: i64,
    pub role: String,
}

pub fn create_token_pair(user_id: i64, role: &str, secret: &str) -> Result<(String, String), jsonwebtoken::errors::Error> {
    let now = Utc::now();
    let access_claims = Claims {
        token_type: "access".into(),
        iat: now.timestamp(),
        exp: (now + Duration::hours(24)).timestamp(),
        jti: Uuid::new_v4().to_string(),
        user_id,
        role: role.to_string(),
    };
    let refresh_claims = Claims {
        token_type: "refresh".into(),
        iat: now.timestamp(),
        exp: (now + Duration::days(7)).timestamp(),
        jti: Uuid::new_v4().to_string(),
        user_id,
        role: role.to_string(),
    };
    let key = EncodingKey::from_secret(secret.as_bytes());
    let access = encode(&Header::default(), &access_claims, &key)?;
    let refresh = encode(&Header::default(), &refresh_claims, &key)?;
    Ok((access, refresh))
}

pub fn decode_claims(token: &str, secret: &str) -> Result<Claims, jsonwebtoken::errors::Error> {
    let mut validation = Validation::default();
    validation.validate_exp = true;
    let data = decode::<Claims>(token, &DecodingKey::from_secret(secret.as_bytes()), &validation)?;
    Ok(data.claims)
}

/// Record a refresh token as outstanding (mirrors SimpleJWT `token_blacklist` tables)
/// so `logout` can blacklist it later.
pub async fn record_outstanding(
    db: &sqlx::SqlitePool,
    user_id: i64,
    jti: &str,
    token: &str,
    exp: i64,
) -> Result<(), sqlx::Error> {
    let now = crate::time::now_str();
    let exp_str = chrono::DateTime::from_timestamp(exp, 0)
        .map(|d| d.naive_utc().to_string())
        .unwrap_or_else(|| now.clone());
    sqlx::query("INSERT INTO token_blacklist_outstandingtoken (user_id, jti, token, created_at, expires_at) VALUES (?, ?, ?, ?, ?)")
        .bind(user_id).bind(jti).bind(token).bind(&now).bind(&exp_str)
        .execute(db).await?;
    Ok(())
}

pub async fn blacklist_jti(db: &sqlx::SqlitePool, jti: &str) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> = sqlx::query_as("SELECT id FROM token_blacklist_outstandingtoken WHERE jti = ?")
        .bind(jti).fetch_optional(db).await?;
    if let Some((id,)) = row {
        let now = crate::time::now_str();
        sqlx::query("INSERT INTO token_blacklist_blacklistedtoken (token_id, blacklisted_at) VALUES (?, ?)")
            .bind(id).bind(&now).execute(db).await?;
        return Ok(true);
    }
    // Fallback: blacklist by raw token lookup happens in handler; unknown jti = false
    Ok(false)
}

pub async fn is_blacklisted(db: &sqlx::SqlitePool, jti: &str) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT b.id FROM token_blacklist_blacklistedtoken b JOIN token_blacklist_outstandingtoken o ON o.id = b.token_id WHERE o.jti = ?")
        .bind(jti).fetch_optional(db).await?;
    Ok(row.is_some())
}

