//! Broadcast delivery worker. Mirrors `broadcast/tasks.py`:
//! `send_broadcast` fans out to every active user (one in-app Notification
//! row each, then one email each), tracking `total` / `sent_count` /
//! `failed_count` and the terminal `sent` / `partial` / `failed` status.
//!
//! Celery mapping:
//! - `send_broadcast.delay(id)` -> `tokio::spawn(send_broadcast(&state, id))`
//! - `send_broadcast_email` (autoretry 3x, 60s backoff) -> per-recipient
//!   attempt loop below (initial try + 3 retries, exponential 60s backoff)
//! - `on_success` / `on_failure` counter bumps -> atomic `SET x = x + 1`
//!   updates followed by the same `_maybe_complete` check.

use askama::Template;

use crate::state::AppState;
use crate::time::now_str;

use super::models::Broadcast;

/// Max email attempts per recipient: initial try + 3 retries (mirrors
/// `BroadcastEmailTask(max_retries=3)`).
const MAX_ATTEMPTS: u32 = 4;
/// Base backoff seconds between retries (mirrors `retry_backoff = 60`).
const BACKOFF_SECS: u64 = 60;

fn static_base(site_url: &str) -> String {
    format!("{}/static", site_url.trim_end_matches('/'))
}

struct TemplateUser {
    first_name: String,
}

#[derive(Template)]
#[template(path = "broadcast/new_month.html")]
struct NewMonthTemplate {
    title: String,
    message: String,
    user: TemplateUser,
    static_base: String,
}

#[derive(Template)]
#[template(path = "broadcast/important.html")]
struct ImportantTemplate {
    title: String,
    message: String,
    user: TemplateUser,
    static_base: String,
}

#[derive(Template)]
#[template(path = "broadcast/announcement.html")]
struct AnnouncementTemplate {
    title: String,
    message: String,
    user: TemplateUser,
    static_base: String,
}

/// Render the broadcast email body. Unknown template names fall back to
/// the announcement layout (views only ever write the three known names).
fn render_email(
    template_name: &str,
    title: &str,
    message: &str,
    first_name: &str,
    static_base: &str,
) -> String {
    let user = TemplateUser { first_name: first_name.to_string() };
    let base = static_base.to_string();
    match template_name {
        "broadcast/important.html" => ImportantTemplate {
            title: title.to_string(),
            message: message.to_string(),
            user,
            static_base: base,
        }
        .render()
        .unwrap_or_else(|_| message.to_string()),
        "broadcast/announcement.html" => AnnouncementTemplate {
            title: title.to_string(),
            message: message.to_string(),
            user,
            static_base: base,
        }
        .render()
        .unwrap_or_else(|_| message.to_string()),
        _ => NewMonthTemplate {
            title: title.to_string(),
            message: message.to_string(),
            user,
            static_base: base,
        }
        .render()
        .unwrap_or_else(|_| message.to_string()),
    }
}

/// Minimal `strip_tags` equivalent for the plaintext part
/// (mirrors `django.utils.html.strip_tags` on the rendered email).
fn strip_tags(html: &str) -> String {
    let mut out = String::with_capacity(html.len());
    let mut in_tag = false;
    for c in html.chars() {
        match c {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ => {
                if !in_tag {
                    out.push(c);
                }
            }
        }
    }
    // Collapse whitespace runs like browsers do for the text part.
    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

async fn bump(
    state: &AppState,
    broadcast_id: i64,
    ok: bool,
) {
    let sql = if ok {
        "UPDATE broadcast_broadcast SET sent_count = sent_count + 1 WHERE id = $1"
    } else {
        "UPDATE broadcast_broadcast SET failed_count = failed_count + 1 WHERE id = $1"
    };
    if let Err(e) = sqlx::query(sql).bind(broadcast_id).execute(&state.db).await {
        tracing::warn!("broadcast {broadcast_id} counter bump failed: {e}");
        return;
    }
    maybe_complete(state, broadcast_id).await;
}

async fn maybe_complete(state: &AppState, broadcast_id: i64) {
    let row: Option<(i64, i64, i64, Option<String>)> = sqlx::query_as(
        "SELECT total, sent_count, failed_count, CAST(completed_at AS TEXT)
         FROM broadcast_broadcast WHERE id = $1",
    )
    .bind(broadcast_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None);
    let Some((total, sent, failed, completed)) = row else {
        return;
    };
    if completed.is_some() || sent + failed < total {
        return;
    }
    let status = if failed == 0 {
        "sent"
    } else if sent == 0 {
        "failed"
    } else {
        "partial"
    };
    if let Err(e) = sqlx::query(
        "UPDATE broadcast_broadcast SET status = $1, completed_at = $2 WHERE id = $3",
    )
    .bind(status)
    .bind(crate::time::Ts(&now_str()))
    .bind(broadcast_id)
    .execute(&state.db)
    .await
    {
        tracing::warn!("broadcast {broadcast_id} completion check failed: {e}");
    }
}

struct Recipient {
    id: i64,
    email: String,
    first_name: String,
}

/// Send one recipient's email with retries. Returns true on delivery.
/// Mirrors `send_broadcast_email` + `BroadcastEmailTask` retry policy.
async fn send_one_email(
    state: &AppState,
    broadcast: &Broadcast,
    recipient: &Recipient,
) -> bool {
    let base = static_base(&state.config.site_url);
    let html = render_email(
        &broadcast.template,
        &broadcast.title,
        &broadcast.message,
        &recipient.first_name,
        &base,
    );
    let plain = strip_tags(&html);
    for attempt in 1..=MAX_ATTEMPTS {
        let ok = crate::email::send_email(
            &state.http,
            &state.config,
            &recipient.email,
            &broadcast.email_subject,
            &plain,
            &html,
        )
        .await;
        if ok {
            if attempt > 1 {
                tracing::info!(
                    "broadcast {} email sent to {} on attempt {attempt}",
                    broadcast.id,
                    recipient.email,
                );
            }
            return true;
        }
        if attempt < MAX_ATTEMPTS {
            // Exponential 60s backoff with jitter (mirrors retry_backoff=60).
            let delay = BACKOFF_SECS * 2_u64.pow(attempt - 1);
            let jitter = (rand_jitter() % 10) + 1;
            tokio::time::sleep(std::time::Duration::from_secs(delay + jitter)).await;
        }
    }
    tracing::error!(
        "broadcast {} email failed for {}",
        broadcast.id,
        recipient.email
    );
    false
}

fn rand_jitter() -> u64 {
    // Cheap jitter without extra deps (nanos-based).
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos() as u64)
        .unwrap_or(7)
}

/// Fan-out worker. Mirrors `broadcast/tasks.py::send_broadcast`.
/// Returns true when the fan-out itself ran (per-recipient failures are
/// tracked on the row, not in the return value).
pub async fn send_broadcast(state: &AppState, broadcast_id: i64) -> bool {
    let row: Option<Broadcast> =
        sqlx::query_as("SELECT * FROM broadcast_broadcast WHERE id = $1")
            .bind(broadcast_id)
            .fetch_optional(&state.db)
            .await
            .unwrap_or(None);
    let Some(broadcast) = row else {
        tracing::error!("broadcast {broadcast_id} not found");
        return false;
    };

    // Duplicate guard: already fanned out (rows exist) while in a live or
    // terminal state -> skip, like Django.
    if ["sending", "sent", "partial"].contains(&broadcast.status.as_str()) {
        let existing: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM notifications_notification WHERE broadcast_id = $1",
        )
        .bind(broadcast_id)
        .fetch_one(&state.db)
        .await
        .unwrap_or((0,));
        if existing.0 > 0 {
            tracing::info!("broadcast {broadcast_id} already fanned out, skipping duplicate");
            maybe_complete(state, broadcast_id).await;
            return true;
        }
    }

    let users: Vec<(i64, String, String, String)> = sqlx::query_as(
        "SELECT id, email, surname, other_names FROM accounts_profile WHERE is_active = TRUE",
    )
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let now = now_str();
    if let Err(e) = sqlx::query(
        "UPDATE broadcast_broadcast
         SET total = $1, sent_count = 0, failed_count = 0, status = 'sending', completed_at = NULL
         WHERE id = $2",
    )
    .bind(users.len() as i64)
    .bind(broadcast_id)
    .execute(&state.db)
    .await
    {
        tracing::error!("broadcast {broadcast_id} fan-out error: {e}");
        return false;
    }

    // Bulk-create in-app rows (500/chunk, like Django's batch_size=500).
    for chunk in users.chunks(500) {
        let mut sql = String::from(
            "INSERT INTO notifications_notification
             (title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id) VALUES ",
        );
        // 5 binds per row: title, message, created_at, user_id, broadcast_id.
        let mut idx = 1;
        let groups: Vec<String> = chunk
            .iter()
            .map(|_| {
                let g = format!("(${idx}, ${}, 'info', FALSE, ${}, NULL, ${}, ${})", idx + 1, idx + 2, idx + 3, idx + 4);
                idx += 5;
                g
            })
            .collect();
        sql.push_str(&groups.join(", "));
        let mut q = sqlx::query(&sql);
        for (id, _, _, _) in chunk {
            q = q
                .bind(&broadcast.title)
                .bind(&broadcast.message)
                .bind(crate::time::Ts(&now))
                .bind(id)
                .bind(broadcast_id);
        }
        if let Err(e) = q.execute(&state.db).await {
            tracing::error!("broadcast {broadcast_id} fan-out error: {e}");
            let _ = sqlx::query(
                "UPDATE broadcast_broadcast SET status = 'failed', completed_at = $1 WHERE id = $2",
            )
            .bind(crate::time::Ts(&now_str()))
            .bind(broadcast_id)
            .execute(&state.db)
            .await;
            return false;
        }
    }

    // Queue one email per user. Sequential like Celery-eager; each email
    // carries its own retry loop, and counters complete the row.
    for (id, email, _surname, other_names) in &users {
        let recipient = Recipient {
            id: *id,
            email: email.clone(),
            // Django passes `other_names` as the template's first_name.
            first_name: other_names.clone(),
        };
        let ok = send_one_email(state, &broadcast, &recipient).await;
        bump(state, broadcast_id, ok).await;
    }
    // Live-push the already-stored rows to connected sockets.
    let rows: Vec<(i64, i64)> = sqlx::query_as(
        "SELECT id, user_id FROM notifications_notification WHERE broadcast_id = $1",
    )
    .bind(broadcast_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    let created = crate::transactions::serializers::format_created_at_lagos(&now_str());
    for (nid, uid) in rows {
        state.notification_hub.publish_notification(
            uid, nid, &broadcast.title, &broadcast.message, "info", &created,
        );
    }
    tracing::info!("broadcast {broadcast_id} queued for {} users", users.len());

    maybe_complete(state, broadcast_id).await;
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn templates_render_title_message_and_name() {
        let base = "https://example.com/static";
        for tpl in [
            "broadcast/new_month.html",
            "broadcast/important.html",
            "broadcast/announcement.html",
        ] {
            let html = render_email(tpl, "Hi T", "Body M", "Ada", base);
            assert!(html.contains("Hi T"), "{tpl}");
            assert!(html.contains("Body M"), "{tpl}");
            assert!(html.contains("Hello Ada"), "{tpl}");
            assert!(html.contains("https://example.com/static/notification/images/logo.jpeg"), "{tpl}");
            assert!(!html.contains("notification_static"), "{tpl}");
        }
    }

    #[test]
    fn empty_name_greets_there() {
        let html = render_email("broadcast/new_month.html", "T", "M", "", "https://x/static");
        assert!(html.contains("Hello there,"), "{html}");
    }

    #[test]
    fn strip_tags_collapses() {
        assert_eq!(strip_tags("<p>Hello <b>World</b></p>"), "Hello World");
    }
}
