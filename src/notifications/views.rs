//! Notification endpoints. Mirrors `notifications/views.py`:
//! newest-first list with `is_read` filter and `unread_count`
//! (20/page default, 50 max), mark read, mark all read, delete.

use std::collections::HashMap;

use axum::{
    Json,
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode, Uri},
};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::models::Notification;
use super::serializers::NotificationPublic;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    get,
    path = "/notifications/",
    tag = "Notifications",
    summary = "List notifications",
    description = "List the authenticated user's notifications, newest first.",
    params(
        ("is_read" = Option<String>, Query, description = "Filter by read status (true/false)"),
        ("page" = Option<i64>, Query, description = "Page number (default 1)"),
        ("page_size" = Option<i64>, Query, description = "Page size (default 20, max 50)"),
    ),
    responses((status = 200, description = "Notification list with unread_count")),
    security(("bearer" = [])),
)]
pub async fn list(
    State(s): State<AppState>,
    headers: HeaderMap,
    uri: Uri,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers.clone()).await?;

    let mut where_sql = "user_id = $1".to_string();
    if let Some(f) = params.get("is_read") {
        // Mirrors Django: any value other than "true" means unread.
        let want = if f.to_lowercase() == "true" { 1 } else { 0 };
        where_sql.push_str(&format!(" AND is_read = {want}"));
    }
    let page = params
        .get("page")
        .and_then(|v| v.parse::<i64>().ok())
        .filter(|p| *p >= 1)
        .unwrap_or(1);
    let size = params
        .get("page_size")
        .and_then(|v| v.parse::<i64>().ok())
        .filter(|sz| *sz >= 1)
        .map(|sz| sz.min(50))
        .unwrap_or(20);

    let count: (i64,) = sqlx::query_as(&format!(
        "SELECT COUNT(*) FROM notifications_notification WHERE {where_sql}"
    ))
    .bind(user.id)
    .fetch_one(&s.db)
    .await?;
    let rows: Vec<Notification> = sqlx::query_as(&format!(
        "SELECT id, title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id
         FROM notifications_notification WHERE {where_sql} ORDER BY created_at DESC LIMIT $2 OFFSET $3"
    ))
    .bind(user.id)
    .bind(size)
    .bind((page - 1) * size)
    .fetch_all(&s.db)
    .await?;

    let mut results = Vec::new();
    for n in &rows {
        let raws: Option<(String, Option<String>)> = sqlx::query_as(
            "SELECT CAST(created_at AS TEXT), CAST(read_at AS TEXT) FROM notifications_notification WHERE id = $1",
        )
        .bind(n.id)
        .fetch_optional(&s.db)
        .await?;
        if let Some((created_raw, read_raw)) = raws {
            results.push(NotificationPublic::from_row(
                n,
                &created_raw,
                read_raw.as_deref(),
            ));
        }
    }

    let unread: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM notifications_notification WHERE user_id = $1 AND is_read = FALSE",
    )
    .bind(user.id)
    .fetch_one(&s.db)
    .await?;

    let host = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("localhost");
    let scheme = headers
        .get("x-forwarded-proto")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("http");
    let total_pages = if count.0 <= 0 { 1 } else { (count.0 + size - 1) / size };
    let link = |p: i64| {
        let mut pairs: Vec<String> = uri
            .query()
            .unwrap_or("")
            .split('&')
            .filter(|s| !s.is_empty())
            .filter(|s| {
                let k = s.split('=').next().unwrap_or("");
                k != "page" && k != "page_size"
            })
            .map(|s| s.to_string())
            .collect();
        pairs.push(format!("page={p}"));
        pairs.push(format!("page_size={size}"));
        format!("{scheme}://{host}{}?{}", uri.path(), pairs.join("&"))
    };

    Ok((
        StatusCode::OK,
        Json(json!({
            "count": count.0,
            "next": if page < total_pages { Some(link(page + 1)) } else { None::<String> },
            "previous": if page > 1 { Some(link(page - 1)) } else { None::<String> },
            "results": results,
            "unread_count": unread.0,
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/notifications/{notification_id}/read/",
    tag = "Notifications",
    summary = "Mark a notification as read",
    params(("notification_id" = i64, Path, description = "Notification ID")),
    responses((status = 200, description = "Marked as read"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn mark_read(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(notification_id): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let row: Option<Notification> = sqlx::query_as(
        "SELECT id, title, message, notification_type, is_read, created_at, read_at, user_id, broadcast_id
         FROM notifications_notification WHERE id = $1 AND user_id = $2",
    )
    .bind(notification_id)
    .bind(user.id)
    .fetch_optional(&s.db)
    .await?;
    let Some(n) = row else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Notification not found"})),
        ));
    };
    // mark_as_read: no-op when already read (read_at untouched).
    if !n.is_read {
        let _ = sqlx::query(
            "UPDATE notifications_notification SET is_read = TRUE, read_at = $1 WHERE id = $2",
        )
        .bind(now_str())
        .bind(n.id)
        .execute(&s.db)
        .await;
    }
    let raws: Option<(String, Option<String>)> = sqlx::query_as(
        "SELECT CAST(created_at AS TEXT), CAST(read_at AS TEXT) FROM notifications_notification WHERE id = $1",
    )
    .bind(n.id)
    .fetch_optional(&s.db)
    .await?;
    let public = raws.map(|(c, r)| {
        let mut updated = n.clone();
        updated.is_read = true;
        NotificationPublic::from_row(&updated, &c, r.as_deref())
    });
    Ok((
        StatusCode::OK,
        Json(json!({"message": "Notification marked as read", "notification": public})),
    ))
}

#[utoipa::path(
    post,
    path = "/notifications/mark-all-read/",
    tag = "Notifications",
    summary = "Mark all notifications as read",
    responses((status = 200, description = "Count marked as read")),
    security(("bearer" = [])),
)]
pub async fn mark_all_read(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let res = sqlx::query(
        "UPDATE notifications_notification SET is_read = TRUE, read_at = $1 WHERE user_id = $2 AND is_read = FALSE",
    )
    .bind(now_str())
    .bind(user.id)
    .execute(&s.db)
    .await?;
    Ok((
        StatusCode::OK,
        Json(json!({"message": format!("{} notifications marked as read", res.rows_affected())})),
    ))
}

#[utoipa::path(
    delete,
    path = "/notifications/{notification_id}/delete/",
    tag = "Notifications",
    summary = "Delete a notification",
    params(("notification_id" = i64, Path, description = "Notification ID")),
    responses((status = 200, description = "Deleted"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn delete(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(notification_id): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let res = sqlx::query(
        "DELETE FROM notifications_notification WHERE id = $1 AND user_id = $2",
    )
    .bind(notification_id)
    .bind(user.id)
    .execute(&s.db)
    .await?;
    if res.rows_affected() == 0 {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Notification not found"})),
        ));
    }
    Ok((
        StatusCode::OK,
        Json(json!({"message": "Notification deleted successfully"})),
    ))
}
