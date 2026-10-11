//! Social authentication providers.
//! Mirrors `accounts/social_auth.py`:
//! `GoogleAuth`, `get_or_create_social_user`.

use serde_json::Value;

use crate::auth::extractor::get_profile;
use crate::auth::password as auth_password;
use crate::error::AppError;

use super::models::Profile;
use super::utils::{now_naive, referral_code};

pub struct SocialUser {
    pub email: String,
    pub email_verified: bool,
    pub given_name: String,
    pub family_name: String,
}

fn tokeninfo_to_user(info: &Value) -> Result<SocialUser, String> {
    let email = info
        .get("email")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    if email.is_empty() {
        return Err("Email is required for social authentication".into());
    }
    Ok(SocialUser {
        email,
        email_verified: info
            .get("email_verified")
            .and_then(|v| v.as_bool())
            .or_else(|| info.get("verified_email").and_then(|v| v.as_bool()))
            .unwrap_or(true),
        given_name: info
            .get("given_name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        family_name: info
            .get("family_name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
    })
}

pub struct GoogleAuth;

impl GoogleAuth {
    /// Verify a Google ID token via the tokeninfo endpoint (client-side flow),
    /// enforcing audience == our GOOGLE_CLIENT_ID like `verify_oauth2_token` does.
    pub async fn verify_google_token(
        http: &reqwest::Client,
        id_token: &str,
        client_id: &str,
    ) -> Result<SocialUser, String> {
        let url = format!("https://oauth2.googleapis.com/tokeninfo?id_token={id_token}");
        let resp = http
            .get(&url)
            .send()
            .await
            .map_err(|e| format!("Google authentication failed: {e}"))?;
        if !resp.status().is_success() {
            return Err("Google authentication failed".into());
        }
        let info: Value = resp
            .json()
            .await
            .map_err(|_| "Google authentication failed".to_string())?;
        if info.get("aud").and_then(|v| v.as_str()) != Some(client_id) {
            return Err("Invalid token audience".into());
        }
        tokeninfo_to_user(&info)
    }

    /// Exchange an authorization code for tokens, then resolve the user
    /// (ID token first, userinfo endpoint fallback).
    pub async fn exchange_code_for_token(
        http: &reqwest::Client,
        client_id: &str,
        client_secret: &str,
        authorization_code: &str,
        redirect_uri: &str,
    ) -> Result<SocialUser, String> {
        if client_secret.is_empty() {
            return Err("Server configuration error".into());
        }
        let params = serde_json::json!({
            "code": authorization_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        });
        let resp = http
            .post("https://oauth2.googleapis.com/token")
            .json(&params)
            .send()
            .await
            .map_err(|_| "Failed to exchange authorization code".to_string())?;
        if !resp.status().is_success() {
            return Err("Failed to exchange authorization code".into());
        }
        let tokens: Value = resp
            .json()
            .await
            .map_err(|_| "Failed to get user information".to_string())?;

        if let Some(idt) = tokens.get("id_token").and_then(|v| v.as_str()) {
            if let Ok(user) = Self::verify_google_token(http, idt, client_id).await {
                return Ok(user);
            }
            // fall through to userinfo endpoint
        }
        if let Some(at) = tokens.get("access_token").and_then(|v| v.as_str()) {
            let r = http
                .get("https://www.googleapis.com/oauth2/v2/userinfo")
                .bearer_auth(at)
                .send()
                .await
                .map_err(|_| "Failed to get user information".to_string())?;
            if !r.status().is_success() {
                return Err("Failed to get user information".into());
            }
            let info: Value = r
                .json()
                .await
                .map_err(|_| "Failed to get user information".to_string())?;
            return tokeninfo_to_user(&info);
        }
        Err("Failed to get user information".into())
    }
}

/// Find the user by email or create one (plus wallet), like
/// `get_or_create_social_user`. Returns `(user, is_new)`.
pub async fn get_or_create_social_user(
    db: &sqlx::PgPool,
    provider: &str,
    social: &SocialUser,
    extra: Option<&Value>,
    phone: Option<&str>,
) -> Result<(Profile, bool), AppError> {
    if let Some(u) = sqlx::query_as::<_, Profile>(
        "SELECT * FROM accounts_profile WHERE email = $1",
    )
    .bind(&social.email)
    .fetch_optional(db)
    .await?
    {
        if !u.email_verified && social.email_verified {
            sqlx::query("UPDATE accounts_profile SET email_verified = TRUE WHERE id = $1")
                .bind(u.id)
                .execute(db)
                .await?;
        }
        if phone.is_some() && u.phone.is_none() {
            sqlx::query("UPDATE accounts_profile SET phone = $1 WHERE id = $2")
                .bind(phone)
                .bind(u.id)
                .execute(db)
                .await?;
        }
        let u2 = get_profile(db, u.id).await?;
        return Ok((u2, false));
    }

    let (surname, other_names) = match provider {
        "google" => (
            social.family_name.clone(),
            if social.given_name.is_empty() {
                social.email.split('@').next().unwrap_or("").to_string()
            } else {
                social.given_name.clone()
            },
        ),
        _ => (
            String::new(),
            social.email.split('@').next().unwrap_or("").to_string(),
        ),
    };

    let now = now_naive().to_string();
    let ref_code = loop {
        let c: String = referral_code();
        let hit: Option<(i64,)> =
            sqlx::query_as("SELECT id FROM accounts_profile WHERE referral_code = $1")
                .bind(&c)
                .fetch_optional(db)
                .await?;
        if hit.is_none() {
            break c;
        }
    };
    let unusable = auth_password::make_unusable();
    let ev = if social.email_verified { 1 } else { 0 };
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO accounts_profile (password, last_login, is_superuser, first_name, last_name, date_joined, email, surname, other_names, phone, image, verification_code, is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, transaction_pin, referral_code, pin_failed_attempts, pin_locked_until, \"has_DVA\")
         VALUES ($1, NULL, 0, '', '', $2, $3, $4, $5, $6, NULL, NULL, 1, 0, 0, 'user', $7, $8, 0, NULL, $9, 0, NULL, 0) RETURNING id")
        .bind(&unusable).bind(crate::time::Ts(&now)).bind(&social.email).bind(&surname).bind(&other_names).bind(phone).bind(ev).bind(crate::time::Ts(&now)).bind(&ref_code)
        .fetch_one(db).await?;
    let uid = res.0;
    sqlx::query("INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id) VALUES ('0.00', '0.00', $1, $2, TRUE, $3)")
        .bind(crate::time::Ts(&now)).bind(crate::time::Ts(&now)).bind(uid).execute(db).await.ok();
    // Mirrors the post_save signal: every user gets a bonus account.
    let _ = crate::bonus::models::ensure_point(db, uid, &now).await;
    Ok((get_profile(db, uid).await?, true))
}
