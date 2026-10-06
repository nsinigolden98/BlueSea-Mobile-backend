//! Notification dispatch. Mirrors `notifications/utils.py::send_notification`:
//! synchronous in-app row, email best-effort (failures logged, never
//! propagated — like Django's try/except around the celery delay).

use askama::Template;

use crate::state::AppState;

fn static_base(site_url: &str) -> String {
    format!("{}/static", site_url.trim_end_matches('/'))
}

fn current_year() -> String {
    chrono::Utc::now().format("%Y").to_string()
}

/// Python `str.title()` equivalent for display fields
/// (uppercases each cased char following an uncased one).
fn py_title(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_cased = false;
    for c in s.chars() {
        if c.is_alphabetic() {
            if prev_cased {
                out.extend(c.to_lowercase());
            } else {
                out.extend(c.to_uppercase());
            }
            prev_cased = true;
        } else {
            out.push(c);
            prev_cased = c.is_numeric();
        }
    }
    out
}

/// Icon class + glyph for the notification type, mirroring the template's
/// `{% if %}` chain (unknown types render no icon, like Django).
fn icon_class(notification_type: &str) -> (&'static str, &'static str) {
    match notification_type {
        "success" | "payment_success" => ("success", "✓"),
        "warning" => ("warning", "⚠"),
        "payment_failed" => ("payment_failed", "✗"),
        "info" => ("info", "ℹ"),
        "payment" => ("payment", "💳"),
        "wallet" => ("wallet", "💰"),
        "group" => ("group", "👥"),
        _ => ("", ""),
    }
}

/// Optional detail block, mirroring the flat `context` dict Django merges
/// into the template context (`{% if context %}` renders only when non-empty).
#[derive(Debug, Default, Clone)]
pub struct NotifyContext {
    pub amount: String,
    pub frequency: String,
    pub group_name: String,
    pub locked_amount: String,
    pub network: String,
    pub next_run: String,
    pub payment_type: String,
    pub phone_number: String,
    pub service_type: String,
    pub start_date: String,
    pub unlocked_amount: String,
    pub vtu_reference: String,
}

impl NotifyContext {
    fn is_empty(&self) -> bool {
        self.amount.is_empty()
            && self.frequency.is_empty()
            && self.group_name.is_empty()
            && self.locked_amount.is_empty()
            && self.network.is_empty()
            && self.next_run.is_empty()
            && self.payment_type.is_empty()
            && self.phone_number.is_empty()
            && self.service_type.is_empty()
            && self.start_date.is_empty()
            && self.unlocked_amount.is_empty()
            && self.vtu_reference.is_empty()
    }
}

struct TemplateUser {
    first_name: String,
}

struct TemplateContext {
    amount: String,
    frequency: String,
    group_name: String,
    locked_amount: String,
    network: String,
    network_upper: String,
    next_run: String,
    payment_type: String,
    payment_type_title: String,
    phone_number: String,
    service_type: String,
    service_type_title: String,
    start_date: String,
    unlocked_amount: String,
    vtu_reference: String,
}

#[derive(Template)]
#[template(path = "notifications/group_payment_contribution.html")]
struct GroupContributionTemplate {
    amount: String,
    group_name: String,
    payment_type_title: String,
    user: TemplateUser,
    static_base: String,
    current_year: String,
}

#[derive(Template)]
#[template(path = "notifications/group_payment_success.html")]
struct GroupSuccessTemplate {
    amount: String,
    group_name: String,
    payment_type: String,
    payment_type_title: String,
    vtu_reference: String,
    user: TemplateUser,
    static_base: String,
    current_year: String,
}

#[derive(Template)]
#[template(path = "notifications/group_payment_failed.html")]
struct GroupFailedTemplate {
    amount: String,
    group_name: String,
    payment_type_title: String,
    reason: String,
    user: TemplateUser,
    static_base: String,
    current_year: String,
}

#[derive(Template)]
#[template(path = "notifications/default_notification.html")]
struct DefaultNotificationTemplate {
    title: String,
    message: String,
    notification_type: String,
    icon_class: String,
    icon_char: String,
    details_heading: String,
    context: TemplateContext,
    user: TemplateUser,
    static_base: String,
    current_year: String,
    has_context: bool,
}

/// Create the in-app notification row and queue the email.
/// Returns the notification id. Email failures are logged only.
pub async fn send_notification(
    state: &AppState,
    user_id: i64,
    user_email: &str,
    first_name: &str,
    title: &str,
    message: &str,
    notification_type: &str,
    email_subject: Option<&str>,
    context: NotifyContext,
) -> Result<i64, sqlx::Error> {
    let now = crate::time::now_str();
    let res = sqlx::query(
        "INSERT INTO notifications_notification (title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id)
         VALUES (?, ?, ?, 0, ?, NULL, ?, NULL)",
    )
    .bind(title)
    .bind(message)
    .bind(notification_type)
    .bind(&now)
    .bind(user_id)
    .execute(&state.db)
    .await?;
    let id = res.last_insert_rowid();

    let html = DefaultNotificationTemplate {
        title: title.to_string(),
        message: message.to_string(),
        notification_type: notification_type.to_string(),
        icon_class: icon_class(notification_type).0.to_string(),
        icon_char: icon_class(notification_type).1.to_string(),
        details_heading: if matches!(
            notification_type,
            "payment" | "payment_success" | "payment_failed" | "wallet"
        ) {
            "Transaction Details:"
        } else {
            "Details:"
        }
        .to_string(),
        user: TemplateUser { first_name: first_name.to_string() },
        static_base: static_base(&state.config.site_url),
        current_year: current_year(),
        has_context: !context.is_empty(),
        context: TemplateContext {
            amount: context.amount.clone(),
            frequency: context.frequency.clone(),
            group_name: context.group_name.clone(),
            locked_amount: context.locked_amount.clone(),
            network: context.network.clone(),
            network_upper: context.network.to_uppercase(),
            next_run: context.next_run.clone(),
            payment_type: context.payment_type.clone(),
            payment_type_title: py_title(&context.payment_type),
            phone_number: context.phone_number.clone(),
            service_type: context.service_type.clone(),
            service_type_title: py_title(&context.service_type),
            start_date: context.start_date.clone(),
            unlocked_amount: context.unlocked_amount.clone(),
            vtu_reference: context.vtu_reference.clone(),
        },
    }
    .render()
    .unwrap_or_else(|_| message.to_string());
    let subject = email_subject.unwrap_or(title);
    deliver(state, user_email, subject, message, &html).await;

    Ok(id)
}

async fn deliver(state: &AppState, user_email: &str, subject: &str, message: &str, html: &str) {
    crate::email::send_email(
        &state.http,
        &state.config,
        user_email,
        subject,
        message,
        html,
    )
    .await;
}

fn base_ctx(state: &AppState) -> (String, String) {
    (
        static_base(&state.config.site_url),
        current_year(),
    )
}

/// Mirrors `contribution_notification`: debited member notice.
pub async fn contribution_notification(
    state: &AppState,
    user_id: i64,
    user_email: &str,
    first_name: &str,
    amount_display: &str,
    group_name: &str,
    payment_type: &str,
) -> Result<i64, sqlx::Error> {
    let title = "Payment Contribution";
    let message = format!("₦{amount_display} debited for {group_name} group payment");
    let now = crate::time::now_str();
    let res = sqlx::query(
        "INSERT INTO notifications_notification (title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id)
         VALUES (?, ?, 'payment', 0, ?, NULL, ?, NULL)",
    )
    .bind(title)
    .bind(&message)
    .bind(&now)
    .bind(user_id)
    .execute(&state.db)
    .await?;
    let id = res.last_insert_rowid();
    let (static_base, current_year) = base_ctx(state);
    let html = GroupContributionTemplate {
        amount: amount_display.to_string(),
        group_name: group_name.to_string(),
        payment_type_title: py_title(payment_type),
        user: TemplateUser { first_name: first_name.to_string() },
        static_base,
        current_year,
    }
    .render()
    .unwrap_or_else(|_| message.clone());
    deliver(state, user_email, "BlueSea Mobile - Payment Contribution", &message, &html).await;
    Ok(id)
}

/// Mirrors `group_payment_success`.
pub async fn group_payment_success(
    state: &AppState,
    user_id: i64,
    user_email: &str,
    first_name: &str,
    amount_display: &str,
    group_name: &str,
    payment_type: &str,
    vtu_reference: &str,
) -> Result<i64, sqlx::Error> {
    let title = "Group Purchase Successful";
    let message = format!("{group_name}: {payment_type} purchase of ₦{amount_display} completed");
    let now = crate::time::now_str();
    let res = sqlx::query(
        "INSERT INTO notifications_notification (title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id)
         VALUES (?, ?, 'payment_success', 0, ?, NULL, ?, NULL)",
    )
    .bind(title)
    .bind(&message)
    .bind(&now)
    .bind(user_id)
    .execute(&state.db)
    .await?;
    let id = res.last_insert_rowid();
    let (static_base, current_year) = base_ctx(state);
    let html = GroupSuccessTemplate {
        amount: amount_display.to_string(),
        group_name: group_name.to_string(),
        payment_type: payment_type.to_string(),
        payment_type_title: py_title(payment_type),
        vtu_reference: vtu_reference.to_string(),
        user: TemplateUser { first_name: first_name.to_string() },
        static_base,
        current_year,
    }
    .render()
    .unwrap_or_else(|_| message.clone());
    deliver(state, user_email, "BlueSea Mobile - Group Purchase Successful", &message, &html).await;
    Ok(id)
}

/// Mirrors `group_payment_failed`.
pub async fn group_payment_failed(
    state: &AppState,
    user_id: i64,
    user_email: &str,
    first_name: &str,
    amount_display: &str,
    group_name: &str,
    payment_type: &str,
    reason: &str,
) -> Result<i64, sqlx::Error> {
    let title = "Group Payment Failed";
    let message = format!("{group_name}: {payment_type} payment failed. ₦{amount_display} has been refunded to your wallet");
    let now = crate::time::now_str();
    let res = sqlx::query(
        "INSERT INTO notifications_notification (title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id)
         VALUES (?, ?, 'payment_failed', 0, ?, NULL, ?, NULL)",
    )
    .bind(title)
    .bind(&message)
    .bind(&now)
    .bind(user_id)
    .execute(&state.db)
    .await?;
    let id = res.last_insert_rowid();
    let (static_base, current_year) = base_ctx(state);
    let html = GroupFailedTemplate {
        amount: amount_display.to_string(),
        group_name: group_name.to_string(),
        payment_type_title: py_title(payment_type),
        reason: reason.to_string(),
        user: TemplateUser { first_name: first_name.to_string() },
        static_base,
        current_year,
    }
    .render()
    .unwrap_or_else(|_| message.clone());
    deliver(state, user_email, "BlueSea Mobile - Group Payment Failed", &message, &html).await;
    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn title_matches_python_semantics() {
        assert_eq!(py_title("airtime"), "Airtime");
        assert_eq!(py_title("dedicated_nuban"), "Dedicated_Nuban");
        assert_eq!(py_title(""), "");
    }

    #[test]
    fn empty_context_renders_without_detail_block() {
        let t = DefaultNotificationTemplate {
            title: "T".into(),
            message: "M".into(),
            notification_type: "payment_success".into(),
            icon_class: icon_class("payment_success").0.into(),
            icon_char: icon_class("payment_success").1.into(),
            details_heading: "Transaction Details:".into(),
            context: TemplateContext {
                amount: String::new(),
                frequency: String::new(),
                group_name: String::new(),
                locked_amount: String::new(),
                network: String::new(),
                network_upper: String::new(),
                next_run: String::new(),
                payment_type: String::new(),
                payment_type_title: String::new(),
                phone_number: String::new(),
                service_type: String::new(),
                service_type_title: String::new(),
                start_date: String::new(),
                unlocked_amount: String::new(),
                vtu_reference: String::new(),
            },
            user: TemplateUser { first_name: "Ada".into() },
            static_base: "https://x/static".into(),
            current_year: "2026".into(),
            has_context: false,
        }
        .render()
        .unwrap();
        assert!(t.contains("Hello Ada"));
        assert!(!t.contains("notification_static"));
        assert!(!t.contains("context."));
    }
}
