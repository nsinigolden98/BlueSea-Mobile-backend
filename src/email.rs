//! Email stub. In DEBUG we log the OTP instead of sending real email
//! (Django sends via SMTP/Brevo). Production wiring (lettre/Brevo) lands later.

pub fn send_otp_email(to_email: &str, subject: &str, otp: &str, debug: bool) -> bool {
    if debug {
        tracing::info!("[DEBUG email] to={to_email} subject={subject} otp/code={otp}");
        return true;
    }
    tracing::info!("email to={to_email} subject={subject}");
    // TODO: wire lettre/Brevo for production
    true
}
