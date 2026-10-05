//! Low-level mail transport.
//!
//! DEBUG: logs the email instead of sending (Django sends via SMTP/Brevo even
//! in dev; we only log until the production transport lands).
//! Production wiring (lettre SMTP / Brevo API) is a TODO here — callers pass
//! fully-rendered subject + plaintext + HTML bodies.

pub fn send_email(
    to_email: &str,
    subject: &str,
    text_body: &str,
    html_body: &str,
    debug: bool,
) -> bool {
    if debug {
        tracing::info!(
            "[DEBUG email] to={to_email} subject={subject} text_len={} html_len={}",
            text_body.len(),
            html_body.len(),
        );
        return true;
    }
    tracing::info!("email to={to_email} subject={subject}");
    // TODO: wire lettre/Brevo for production
    true
}
