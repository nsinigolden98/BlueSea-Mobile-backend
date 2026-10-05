//! Per-account transaction-PIN lockout.
//! Mirrors `accounts/pin_security.py::verify_pin_with_lockout`.

use chrono::Utc;

use super::crypto::decrypt_pin;
use super::models::Profile;
use crate::auth::password as auth_password;

pub struct PinResult {
    pub ok: bool,
    pub locked: bool,
    /// Seconds until the lock expires (0 when not locked).
    pub retry_after: i64,
    pub attempts_remaining: i64,
}

/// Verify an RSA-encrypted transaction PIN while enforcing per-account lockout.
///
/// - Returns `locked=true` when the account is currently locked (no decrypt attempted).
/// - On success resets the failure counter.
/// - On failure increments the counter and locks the account after
///   `max_attempts` consecutive failures for `lockout_minutes`.
pub async fn verify_pin_with_lockout(
    db: &sqlx::SqlitePool,
    user_id: i64,
    encrypted_pin: &str,
    pin_key: &str,
    max_attempts: i64,
    lockout_minutes: i64,
) -> Result<PinResult, sqlx::Error> {
    let user: Option<Profile> =
        sqlx::query_as("SELECT * FROM accounts_profile WHERE id = ?")
            .bind(user_id)
            .fetch_optional(db)
            .await?;
    let Some(user) = user else {
        return Ok(PinResult {
            ok: false,
            locked: false,
            retry_after: 0,
            attempts_remaining: 0,
        });
    };
    let now_ts = Utc::now().timestamp();

    // Currently locked?
    if let Some(locked_until) = user.pin_locked_until {
        if locked_until.and_utc().timestamp() > now_ts {
            return Ok(PinResult {
                ok: false,
                locked: true,
                retry_after: locked_until.and_utc().timestamp() - now_ts,
                attempts_remaining: 0,
            });
        }
    }

    // Expired lock -> clear so the user gets a fresh attempt budget.
    if user
        .pin_locked_until
        .map(|t| t.and_utc().timestamp() <= now_ts)
        .unwrap_or(false)
    {
        sqlx::query(
            "UPDATE accounts_profile SET pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?",
        )
        .bind(user.id)
        .execute(db)
        .await?;
    }

    let verified = match decrypt_pin(encrypted_pin, pin_key) {
        Ok(plain) => user
            .transaction_pin
            .as_deref()
            .map(|h| auth_password::verify_password(&plain, h))
            .unwrap_or(false),
        Err(_) => false,
    };

    if verified {
        sqlx::query(
            "UPDATE accounts_profile SET pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?",
        )
        .bind(user.id)
        .execute(db)
        .await?;
        return Ok(PinResult {
            ok: true,
            locked: false,
            retry_after: 0,
            attempts_remaining: max_attempts,
        });
    }

    // Failed attempt.
    let attempts = user.pin_failed_attempts + 1;
    let attempts_remaining = (max_attempts - attempts).max(0);
    if attempts >= max_attempts {
        let until = (Utc::now() + chrono::Duration::minutes(lockout_minutes))
            .naive_utc()
            .to_string();
        sqlx::query(
            "UPDATE accounts_profile SET pin_failed_attempts = ?, pin_locked_until = ? WHERE id = ?",
        )
        .bind(attempts)
        .bind(&until)
        .bind(user.id)
        .execute(db)
        .await?;
        return Ok(PinResult {
            ok: false,
            locked: true,
            retry_after: lockout_minutes * 60,
            attempts_remaining: 0,
        });
    }
    sqlx::query("UPDATE accounts_profile SET pin_failed_attempts = ? WHERE id = ?")
        .bind(attempts)
        .bind(user.id)
        .execute(db)
        .await?;
    Ok(PinResult {
        ok: false,
        locked: false,
        retry_after: 0,
        attempts_remaining,
    })
}
