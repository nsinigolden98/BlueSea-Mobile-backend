//! Broadcast endpoints. Mirrors `broadcast/views.py`: superuser-gated
//! (`is_superuser`, otherwise 403) preview-or-queue sends for the three
//! kinds plus newest-first history. All responses are `Cache-Control:
//! no-store`, like Django.

use std::collections::HashMap;

use axum::{
    Json,
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::models as m;
use super::serializers as s;
use super::tasks;

type Resp = (StatusCode, HeaderMap, Json<Value>);

pub const NEW_MONTH_TEMPLATE: &str = "broadcast/new_month.html";
pub const IMPORTANT_TEMPLATE: &str = "broadcast/important.html";
pub const ANNOUNCEMENT_TEMPLATE: &str = "broadcast/announcement.html";

fn no_store(status: StatusCode, body: Value) -> Resp {
    let mut headers = HeaderMap::new();
    headers.insert("cache-control", "no-store, no-cache, must-revalidate, max-age=0".parse().unwrap());
    headers.insert("pragma", "no-cache".parse().unwrap());
    (status, headers, Json(body))
}

fn forbidden() -> Resp {
    no_store(
        StatusCode::FORBIDDEN,
        json!({"detail": "You do not have permission to perform this action."}),
    )
}

async fn require_superuser(s: &AppState, headers: HeaderMap) -> Result<crate::accounts::models::Profile, Resp> {
    let user = auth_user(State(s.clone()), headers).await.map_err(|e| {
        no_store(StatusCode::UNAUTHORIZED, json!({"detail": e.message}))
    })?;
    if !user.is_superuser {
        return Err(forbidden());
    }
    Ok(user)
}

/// Django `timezone.now()` formats in UTC (aware UTC datetime), so month
/// keys/names are UTC-based, matching Django exactly.
fn current_month_key() -> String {
    chrono::Utc::now().format("%Y-%m").to_string()
}

fn current_month_name() -> String {
    chrono::Utc::now().format("%B %Y").to_string()
}

fn new_month_defaults(params: &HashMap<String, String>) -> (String, String, String) {
    let month_name = current_month_name();
    let title = params.get("title").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| format!("Happy New Month — {month_name}!"));
    let message = params.get("message").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| {
        format!(
            "Happy New Month, and welcome to {month_name}! Thank you for choosing BlueSea Mobile. May this new month bring you joy, growth, and seamless transactions."
        )
    });
    let email_subject = params.get("email_subject").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| format!("BlueSea Mobile — {title}"));
    (title, message, email_subject)
}

fn important_defaults(params: &HashMap<String, String>) -> (String, String, String) {
    let title = params.get("title").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| "Important: We have moved to blueseamobile.com".to_string());
    let message = params.get("message").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| {
        "Hello from BlueSea Mobile! Please note our platform has moved from blueseamobile.com.ng to blueseamobile.com. Please update your bookmarks and always use blueseamobile.com going forward. Your account, wallet balance, and PIN remain unchanged.".to_string()
    });
    let email_subject = params.get("email_subject").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| "BlueSea Mobile — Important domain change".to_string());
    (title, message, email_subject)
}

fn announcement_defaults(params: &HashMap<String, String>) -> (String, String, String) {
    let title = params.get("title").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| "Thank You for Celebrating with Us!".to_string());
    let message = params.get("message").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| {
        "Thank you for coming out on Saturday, October 3rd! Your presence at the BlueSea Mobile event — red carpet at 2:30pm, main event at 3:00pm, at Assemblies of God, Testimony Chapel, Oyigbo, Rivers State — meant the world to us. We're grateful for this community and have so much more in store. Stay tuned!".to_string()
    });
    let email_subject = params.get("email_subject").cloned().filter(|v| !v.is_empty()).unwrap_or_else(|| "BlueSea Mobile — Thank You!".to_string());
    (title, message, email_subject)
}

fn confirmed(params: &HashMap<String, String>) -> bool {
    params.get("confirm").map(|v| v.to_lowercase() == "yes").unwrap_or(false)
}

fn forced(params: &HashMap<String, String>) -> bool {
    params.get("force").map(|v| v.to_lowercase() == "yes").unwrap_or(false)
}

async fn queue_broadcast(
    s: &AppState,
    user_id: i64,
    kind: &str,
    title: &str,
    message: &str,
    email_subject: &str,
    template: &str,
    month_key: Option<&str>,
) -> Result<m::Broadcast, AppError> {
    let total = m::recipient_count(&s.db).await?;
    let now = now_str();
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO broadcast_broadcast
         (kind, title, message, email_subject, template, month_key, status, total, sent_count, failed_count, created_by_id, created_at, completed_at)
         VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, 0, 0, $8, $9, NULL) RETURNING id",
    )
    .bind(kind)
    .bind(title)
    .bind(message)
    .bind(email_subject)
    .bind(template)
    .bind(month_key)
    .bind(total)
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(&s.db)
    .await?;
    let id = res.0;
    // Celery `send_broadcast.delay(id)` becomes a detached Tokio task; the
    // record is returned immediately with HTTP 202 either way.
    let bg = s.clone();
    tokio::spawn(async move {
        tasks::send_broadcast(&bg, id).await;
    });
    sqlx::query_as::<_, m::Broadcast>("SELECT * FROM broadcast_broadcast WHERE id = $1")
        .bind(id)
        .fetch_one(&s.db)
        .await
        .map_err(AppError::from)
}

#[utoipa::path(
    get,
    path = "/broadcast/new-month/",
    tag = "Broadcast",
    summary = "Broadcast Happy New Month (superuser)",
    description = "Preview the monthly greeting, or queue it with ?confirm=yes (202). One send per month unless ?force=yes.",
    params(
        ("confirm" = Option<String>, Query, description = "Set to 'yes' to queue the broadcast"),
        ("force" = Option<String>, Query, description = "Set to 'yes' to resend this month"),
        ("title" = Option<String>, Query, description = "Override the greeting title"),
        ("message" = Option<String>, Query, description = "Override the greeting body"),
        ("email_subject" = Option<String>, Query, description = "Override the email subject"),
    ),
    responses((status = 200, description = "Dry-run preview"), (status = 202, description = "Queued"), (status = 400, description = "Already sent"), (status = 403, description = "Superuser only")),
    security(("bearer" = [])),
)]
pub async fn new_month(
    State(s): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = match require_superuser(&s, headers).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let month_key = current_month_key();
    let (title, message, email_subject) = new_month_defaults(&params);
    let already_sent = m::already_sent(&s.db, "new_month", Some(&month_key)).await?;
    if !confirmed(&params) {
        return Ok(no_store(StatusCode::OK, json!({
            "kind": "new_month",
            "month_key": month_key,
            "title": title,
            "message": message,
            "email_subject": email_subject,
            "template": NEW_MONTH_TEMPLATE,
            "recipient_count": m::recipient_count(&s.db).await?,
            "already_sent": already_sent,
            "hint": "Add ?confirm=yes to queue the broadcast",
        })));
    }
    if already_sent && !forced(&params) {
        return Ok(no_store(StatusCode::BAD_REQUEST, json!({
            "error": format!("New month broadcast for {month_key} already sent. Use ?force=yes to resend.")
        })));
    }
    let b = queue_broadcast(&s, user.id, "new_month", &title, &message, &email_subject, NEW_MONTH_TEMPLATE, Some(&month_key)).await?;
    let public = s::broadcast_public(&s.db, &b).await;
    Ok(no_store(StatusCode::ACCEPTED, serde_json::to_value(&public).unwrap_or(Value::Null)))
}

#[utoipa::path(
    get,
    path = "/broadcast/important/",
    tag = "Broadcast",
    summary = "Broadcast important notice (superuser)",
    description = "Preview the domain-change notice, or queue it with ?confirm=yes (202). One-shot unless ?force=yes.",
    params(
        ("confirm" = Option<String>, Query, description = "Set to 'yes' to queue the broadcast"),
        ("force" = Option<String>, Query, description = "Set to 'yes' to resend"),
        ("title" = Option<String>, Query, description = "Override the notice title"),
        ("message" = Option<String>, Query, description = "Override the notice body"),
        ("email_subject" = Option<String>, Query, description = "Override the email subject"),
    ),
    responses((status = 200, description = "Dry-run preview"), (status = 202, description = "Queued"), (status = 400, description = "Already sent"), (status = 403, description = "Superuser only")),
    security(("bearer" = [])),
)]
pub async fn important(
    State(s): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = match require_superuser(&s, headers).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let (title, message, email_subject) = important_defaults(&params);
    let already_sent = m::already_sent(&s.db, "important", None).await?;
    if !confirmed(&params) {
        return Ok(no_store(StatusCode::OK, json!({
            "kind": "important",
            "title": title,
            "message": message,
            "email_subject": email_subject,
            "template": IMPORTANT_TEMPLATE,
            "recipient_count": m::recipient_count(&s.db).await?,
            "already_sent": already_sent,
            "hint": "Add ?confirm=yes to queue the broadcast",
        })));
    }
    if already_sent && !forced(&params) {
        return Ok(no_store(StatusCode::BAD_REQUEST, json!({
            "error": "Important broadcast already sent. Use ?force=yes to resend."
        })));
    }
    let b = queue_broadcast(&s, user.id, "important", &title, &message, &email_subject, IMPORTANT_TEMPLATE, None).await?;
    let public = s::broadcast_public(&s.db, &b).await;
    Ok(no_store(StatusCode::ACCEPTED, serde_json::to_value(&public).unwrap_or(Value::Null)))
}

#[utoipa::path(
    get,
    path = "/broadcast/announcement/",
    tag = "Broadcast",
    summary = "Broadcast general announcement (superuser)",
    description = "Preview the announcement, or queue it with ?confirm=yes (202). One-shot unless ?force=yes.",
    params(
        ("confirm" = Option<String>, Query, description = "Set to 'yes' to queue the broadcast"),
        ("force" = Option<String>, Query, description = "Set to 'yes' to send a new announcement"),
        ("title" = Option<String>, Query, description = "Override the announcement title"),
        ("message" = Option<String>, Query, description = "Override the announcement body"),
        ("email_subject" = Option<String>, Query, description = "Override the email subject"),
    ),
    responses((status = 200, description = "Dry-run preview"), (status = 202, description = "Queued"), (status = 400, description = "Already sent"), (status = 403, description = "Superuser only")),
    security(("bearer" = [])),
)]
pub async fn announcement(
    State(s): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = match require_superuser(&s, headers).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let (title, message, email_subject) = announcement_defaults(&params);
    let already_sent = m::already_sent(&s.db, "announcement", None).await?;
    if !confirmed(&params) {
        return Ok(no_store(StatusCode::OK, json!({
            "kind": "announcement",
            "title": title,
            "message": message,
            "email_subject": email_subject,
            "template": ANNOUNCEMENT_TEMPLATE,
            "recipient_count": m::recipient_count(&s.db).await?,
            "already_sent": already_sent,
            "hint": "Add ?confirm=yes to queue the broadcast",
        })));
    }
    if already_sent && !forced(&params) {
        return Ok(no_store(StatusCode::BAD_REQUEST, json!({
            "error": "Announcement already sent. Use ?force=yes to send a new one."
        })));
    }
    let b = queue_broadcast(&s, user.id, "announcement", &title, &message, &email_subject, ANNOUNCEMENT_TEMPLATE, None).await?;
    let public = s::broadcast_public(&s.db, &b).await;
    Ok(no_store(StatusCode::ACCEPTED, serde_json::to_value(&public).unwrap_or(Value::Null)))
}

#[utoipa::path(
    get,
    path = "/broadcast/",
    tag = "Broadcast",
    summary = "List broadcasts (superuser)",
    description = "Newest-first history of queued broadcasts (latest 50) with delivery counters.",
    responses((status = 200, description = "Broadcast history"), (status = 403, description = "Superuser only")),
    security(("bearer" = [])),
)]
pub async fn history(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let _user = match require_superuser(&s, headers).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let rows: Vec<m::Broadcast> = sqlx::query_as(
        "SELECT * FROM broadcast_broadcast ORDER BY created_at DESC LIMIT 50",
    )
    .fetch_all(&s.db)
    .await?;
    let mut out = Vec::new();
    for b in &rows {
        out.push(s::broadcast_public(&s.db, b).await);
    }
    Ok(no_store(StatusCode::OK, Value::Array(out.into_iter().map(|v| serde_json::to_value(v).unwrap_or(Value::Null)).collect())))
}
