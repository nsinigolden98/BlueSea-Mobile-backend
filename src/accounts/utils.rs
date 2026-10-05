//! Small shared helpers for the accounts app.
//! Mirrors the utility bits of `accounts/utils.py`
//! (`send_email_verification`, OTP/referral generation).

use chrono::{NaiveDateTime, Utc};
use rand::Rng;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

pub fn now_naive() -> NaiveDateTime {
    Utc::now().naive_utc()
}

pub fn six_digit_otp() -> String {
    rand::thread_rng().gen_range(100000..=999999).to_string()
}

/// 6-char uppercase hex referral code (`secrets.token_hex(3).upper()`).
pub fn referral_code() -> String {
    let bytes: [u8; 3] = rand::random();
    hex::encode(bytes).to_uppercase()
}

/// Thin wrapper over the mail transport that logs the OTP in DEBUG,
/// like Django's `send_email_verification` (subject/template/context).
pub fn send_email_verification(to_email: &str, subject: &str, otp: &str, debug: bool) -> bool {
    crate::email::send_otp_email(to_email, subject, otp, debug)
}

/// Own signed-token format for the password-reset flow
/// (`payload_b64.sig_b64`, 900s expiry).
///
/// NOTE: tokens issued by Django are not accepted here and vice versa; the full
/// request → verify → confirm flow must happen against the same backend.
pub mod reset_token {
    use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD as B64U};
    use hmac::{Hmac, Mac};
    use sha2::Sha256;

    pub fn issue(secret: &str, email: &str) -> String {
        let payload =
            serde_json::json!({"email": email, "ts": chrono::Utc::now().timestamp()})
                .to_string();
        let p = B64U.encode(payload.as_bytes());
        let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
        mac.update(p.as_bytes());
        format!("{p}.{}", B64U.encode(mac.finalize().into_bytes()))
    }

    pub fn verify(secret: &str, token: &str, max_age_secs: i64) -> Result<String, &'static str> {
        let (p, sig) = token.split_once('.').ok_or("Invalid reset token")?;
        let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
        mac.update(p.as_bytes());
        let expect = B64U.encode(mac.finalize().into_bytes());
        if !bool::from(subtle::ConstantTimeEq::ct_eq(
            expect.as_bytes(),
            sig.as_bytes(),
        )) {
            return Err("Invalid reset token");
        }
        let raw = B64U.decode(p).map_err(|_| "Invalid reset token")?;
        let v: serde_json::Value =
            serde_json::from_slice(&raw).map_err(|_| "Invalid reset token")?;
        let ts = v
            .get("ts")
            .and_then(|t| t.as_i64())
            .ok_or("Invalid reset token")?;
        if chrono::Utc::now().timestamp() - ts > max_age_secs {
            return Err("Reset token has expired");
        }
        v.get("email")
            .and_then(|e| e.as_str())
            .map(|s| s.to_string())
            .ok_or("Invalid reset token")
    }
}

// In-memory PIN-reset OTP/token store (mirrors Django cache 600s/300s TTLs).
pub struct PinResetStore {
    pub otps: HashMap<String, (String, i64)>,
    pub tokens: HashMap<String, (String, i64)>,
}

static PIN_STORE: OnceLock<Mutex<PinResetStore>> = OnceLock::new();

pub fn pin_store() -> &'static Mutex<PinResetStore> {
    PIN_STORE.get_or_init(|| {
        Mutex::new(PinResetStore {
            otps: HashMap::new(),
            tokens: HashMap::new(),
        })
    })
}
