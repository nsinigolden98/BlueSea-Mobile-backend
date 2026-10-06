//! Mail transport.
//!
//! Backends (selected by `EMAIL_BACKEND`, like Django):
//! - `console` (default in DEBUG): logs the email, sends nothing.
//! - `brevo` (default in production): Brevo transactional HTTP API
//!   (`POST https://api.brevo.com/v3/smtp/email`), mirroring what
//!   `django-anymail` does with `BREVO_API_KEY` today.
//!
//! Production SMTP via `lettre` is intentionally not wired: Brevo is the prod
//! backend. Callers pass fully-rendered subject + plaintext + HTML bodies.

use crate::settings::Config;

/// Pure constructor for the Brevo `sendTransacEmail` payload, unit-tested.
pub fn brevo_payload(
    from_email: &str,
    to_email: &str,
    subject: &str,
    text_body: &str,
    html_body: &str,
) -> serde_json::Value {
    serde_json::json!({
        "sender": {"name": "BlueSea Mobile", "email": from_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    })
}

async fn send_via_brevo(
    http: &reqwest::Client,
    config: &Config,
    to_email: &str,
    subject: &str,
    text_body: &str,
    html_body: &str,
) -> bool {
    if config.brevo_api_key.trim().is_empty() {
        tracing::error!("email to={to_email} not sent: BREVO_API_KEY is not configured");
        return false;
    }
    let payload = brevo_payload(
        &config.from_email,
        to_email,
        subject,
        text_body,
        html_body,
    );
    match http
        .post("https://api.brevo.com/v3/smtp/email")
        .header("api-key", config.brevo_api_key.trim())
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
    {
        Ok(resp) => {
            if resp.status().is_success() {
                tracing::info!("email sent via brevo to={to_email} subject={subject}");
                true
            } else {
                tracing::error!(
                    "brevo send failed to={to_email} status={} body={}",
                    resp.status(),
                    resp.text().await.unwrap_or_default()
                );
                false
            }
        }
        Err(e) => {
            tracing::error!("brevo send error to={to_email}: {e}");
            false
        }
    }
}

pub async fn send_email(
    http: &reqwest::Client,
    config: &Config,
    to_email: &str,
    subject: &str,
    text_body: &str,
    html_body: &str,
) -> bool {
    if config.email_backend.trim().eq_ignore_ascii_case("brevo") {
        return send_via_brevo(http, config, to_email, subject, text_body, html_body).await;
    }
    // console backend (dev default): log and pretend success, like before.
    tracing::info!(
        "[DEBUG email] to={to_email} subject={subject} text_len={} html_len={}",
        text_body.len(),
        html_body.len(),
    );
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn payload_shape_matches_brevo_api() {
        let p = brevo_payload("noreply@bluesea.com", "a@b.com", "Sub", "plain", "<b>html</b>");
        assert_eq!(p["sender"]["name"], "BlueSea Mobile");
        assert_eq!(p["sender"]["email"], "noreply@bluesea.com");
        assert_eq!(p["to"][0]["email"], "a@b.com");
        assert_eq!(p["subject"], "Sub");
        assert_eq!(p["textContent"], "plain");
        assert_eq!(p["htmlContent"], "<b>html</b>");
    }
}
