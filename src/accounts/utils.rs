//! Small shared helpers for the accounts app.
//! Mirrors the utility bits of `accounts/utils.py`
//! (`send_email_verification`, OTP/referral generation).
//!
//! HTML bodies are rendered from Askama templates in `templates/accounts/`,
//! converted 1:1 from `accounts/templates/accounts/*.html`
//! (`{% email_static %}` → `{{ static_base }}` absolute URLs).

use askama::Template;
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

fn static_base(site_url: &str) -> String {
    format!("{}/static", site_url.trim_end_matches('/'))
}

fn current_year() -> String {
    Utc::now().format("%Y").to_string()
}

// ---------- email templates (one struct per Django template) ----------

#[derive(Template)]
#[template(path = "accounts/signup_email_verify.html")]
struct SignupTemplate {
    email: String,
    verification_code: String,
    static_base: String,
}

#[derive(Template)]
#[template(path = "accounts/password_reset.html")]
struct PasswordResetTemplate {
    email: String,
    token: String,
    static_base: String,
    current_year: String,
}

#[derive(Template)]
#[template(path = "accounts/password_reset_success.html")]
struct PasswordResetSuccessTemplate {
    static_base: String,
}

#[derive(Template)]
#[template(path = "accounts/pin_reset.html")]
struct PinResetTemplate {
    email: String,
    token: String,
    static_base: String,
    current_year: String,
}

pub struct RenderedEmail {
    pub to: String,
    pub subject: &'static str,
    pub text: String,
    pub html: String,
}

pub fn signup_verification_email(site_url: &str, to_email: &str, otp: &str) -> RenderedEmail {
    let html = SignupTemplate {
        email: to_email.to_string(),
        verification_code: otp.to_string(),
        static_base: static_base(site_url),
    }
    .render()
    .expect("signup template renders");
    let text = format!(
        "BlueSea VTU - Verify Your Email Address\n\nPlease use the OTP below to verify your email address \
         and complete your account registration.\n\nOTP: {otp}\n\nNote: This OTP is valid for only 15 minutes \
         from when you received it.\n\nIf you didn't request this email, you can safely ignore it.\n\n\
         Need help? Contact our support at support@bluesea.com"
    );
    RenderedEmail {
        to: to_email.to_string(),
        subject: "Verify Email Address",
        text,
        html,
    }
}

pub fn password_reset_email(site_url: &str, to_email: &str, otp: &str) -> RenderedEmail {
    let html = PasswordResetTemplate {
        email: to_email.to_string(),
        token: otp.to_string(),
        static_base: static_base(site_url),
        current_year: current_year(),
    }
    .render()
    .expect("password reset template renders");
    let text = format!(
        "BlueSea VTU - Password Reset\n\nWe received a request to reset the password for {to_email}.\n\n\
         OTP: {otp}\n\nThis OTP is valid for 10 minutes. If you didn't request this, please ignore this email."
    );
    RenderedEmail {
        to: to_email.to_string(),
        subject: "Password Reset Verification Code",
        text,
        html,
    }
}

pub fn password_reset_success_email(site_url: &str, to_email: &str) -> RenderedEmail {
    let html = PasswordResetSuccessTemplate {
        static_base: static_base(site_url),
    }
    .render()
    .expect("password reset success template renders");
    RenderedEmail {
        to: to_email.to_string(),
        subject: "Password Reset Successful",
        text: "Your BlueSea account password has been successfully reset. You can now log in with your new password."
            .to_string(),
        html,
    }
}

pub fn pin_reset_email(site_url: &str, to_email: &str, otp: &str) -> RenderedEmail {
    let html = PinResetTemplate {
        email: to_email.to_string(),
        token: otp.to_string(),
        static_base: static_base(site_url),
        current_year: current_year(),
    }
    .render()
    .expect("pin reset template renders");
    let text = format!(
        "BlueSea VTU - Transaction PIN Reset\n\nUse the OTP below to reset your transaction PIN for {to_email}.\n\n\
         OTP: {otp}\n\nThis OTP is valid for 10 minutes. If you didn't request this, please ignore this email."
    );
    RenderedEmail {
        to: to_email.to_string(),
        subject: "Transaction Pin Reset Verification Code",
        text,
        html,
    }
}

/// Rendered-email sender (mirrors `send_email_verification`).
/// DEBUG logs the email; production transport lands in `crate::email`.
pub fn send_rendered_email(email: &RenderedEmail, debug: bool) -> bool {
    crate::email::send_email(&email.to, email.subject, &email.text, &email.html, debug)
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

#[cfg(test)]
mod tests {
    use super::*;

    const SITE: &str = "https://api.blueseamobile.com";

    #[test]
    fn signup_renders_otp_and_static_urls() {
        let e = signup_verification_email(SITE, "a@b.com", "123456");
        assert!(e.html.contains("123456"));
        assert!(e.html.contains("https://api.blueseamobile.com/static/accounts/images/logo.jpeg"));
        assert!(!e.html.contains("email_static"));
        assert!(e.text.contains("123456"));
    }

    #[test]
    fn password_reset_renders_token_and_email() {
        let e = password_reset_email(SITE, "a@b.com", "654321");
        assert!(e.html.contains("654321"));
        assert!(e.html.contains("a@b.com"));
        assert!(!e.html.contains("email_static"));
        assert!(!e.html.contains("current_year"));
    }

    #[test]
    fn password_reset_success_renders() {
        let e = password_reset_success_email(SITE, "a@b.com");
        assert!(e.html.contains("Password Reset Successful"));
        assert!(!e.html.contains("email_static"));
    }

    #[test]
    fn pin_reset_renders_token_and_email() {        let e = pin_reset_email(SITE, "a@b.com", "112233");
        assert!(e.html.contains("112233"));
        assert!(e.html.contains("a@b.com"));
        assert!(!e.html.contains("email_static"));
    }
}
