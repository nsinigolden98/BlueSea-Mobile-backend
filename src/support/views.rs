//! Support REST endpoints. Mirrors `support/views.py` (user tickets)
//! and `support/admin_view.py` (admin tickets, `is_admin` gate).

use std::collections::HashMap;

use axum::{
    Json,
    extract::{FromRequest, Multipart, Path, Query, Request, State},
    http::{HeaderMap, StatusCode, header::CONTENT_TYPE},
};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::models as m;
use super::serializers as s;

type Resp = (StatusCode, Json<Value>);

fn scheme_host(headers: &HeaderMap) -> (String, String) {
    let host = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("localhost")
        .to_string();
    let scheme = headers
        .get("x-forwarded-proto")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("http")
        .to_string();
    (scheme, host)
}

fn forbidden() -> Resp {
    (
        StatusCode::FORBIDDEN,
        Json(json!({"detail": "You do not have permission to perform this action."})),
    )
}

fn not_found() -> Resp {
    (StatusCode::NOT_FOUND, Json(json!({"error": "Ticket not found"})))
}

const IMAGE_EXTS: &[&str] = &["png", "jpg", "jpeg", "webp", "gif"];

async fn store_support_upload(
    media_root: &str,
    filename: &str,
    bytes: &[u8],
) -> Option<String> {
    if bytes.is_empty() || bytes.len() > 5 * 1024 * 1024 {
        return None;
    }
    let ext = filename.rsplit('.').next().unwrap_or("").to_lowercase();
    if !IMAGE_EXTS.contains(&ext.as_str()) {
        return None;
    }
    let ext = if ext == "jpeg" { "jpg".to_string() } else { ext };
    let now = chrono::Utc::now();
    let dir = format!("support_attachments/{}/{:02}/{:02}", now.format("%Y"), now.format("%m"), now.format("%d"));
    let stored = format!("{dir}/{}.{}", uuid::Uuid::new_v4().simple(), ext);
    let path = std::path::Path::new(media_root).join(&stored);
    if let Some(parent) = path.parent() {
        if tokio::fs::create_dir_all(parent).await.is_err() {
            return None;
        }
    }
    if tokio::fs::write(&path, bytes).await.is_err() {
        return None;
    }
    Some(stored)
}

struct ParsedForm {
    fields: HashMap<String, String>,
    images: Vec<(String, Vec<u8>)>,
}

async fn parse_form(mut req: Request, max_bytes: usize) -> Result<ParsedForm, AppError> {
    let is_multipart = req
        .headers()
        .get(CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .map(|ct| ct.starts_with("multipart/"))
        .unwrap_or(false);
    let mut out = ParsedForm { fields: HashMap::new(), images: Vec::new() };
    if is_multipart {
        let mut multipart = Multipart::from_request(req, &()).await.map_err(|_| {
            AppError::bad_request("Invalid multipart body")
        })?;
        while let Ok(Some(field)) = multipart.next_field().await {
            let name = field.name().unwrap_or("").to_string();
            let filename = field.file_name().map(|f| f.to_string());
            match field.bytes().await {
                Ok(bytes) => {
                    if let Some(fname) = filename {
                        if name == "images" {
                            out.images.push((fname, bytes.to_vec()));
                        }
                    } else if let Ok(text) = String::from_utf8(bytes.to_vec()) {
                        out.fields.entry(name).or_insert(text);
                    }
                }
                Err(_) => continue,
            }
        }
        return Ok(out);
    }
    let body = axum::body::to_bytes(req.into_body(), max_bytes).await.unwrap_or_default();
    if !body.is_empty() {
        if let Ok(Value::Object(map)) = serde_json::from_slice::<Value>(&body) {
            for (k, v) in map {
                match v {
                    Value::String(text) => {
                        out.fields.insert(k, text);
                    }
                    Value::Number(n) => {
                        out.fields.insert(k, n.to_string());
                    }
                    Value::Array(items) => {
                        // `images: []` in JSON carries no bytes; keep marker only.
                        if k == "images" && out.images.is_empty() {
                            let _ = items;
                        }
                    }
                    _ => {}
                }
            }
        }
    }
    Ok(out)
}

async fn save_images(
    db: &sqlx::PgPool,
    media_root: &str,
    message_id: i64,
    images: &[(String, Vec<u8>)],
    now: &str,
) -> Result<(), AppError> {
    for (filename, bytes) in images {
        let Some(stored) = store_support_upload(media_root, filename, bytes).await else {
            return Err(AppError::bad_request(format!("Invalid image '{filename}'")));
        };
        sqlx::query(
            "INSERT INTO support_supportattachment (image, uploaded_at, message_id) VALUES ($1, $2, $3)",
        )
        .bind(&stored)
        .bind(crate::time::Ts(&now))
        .bind(message_id)
        .execute(db)
        .await?;
    }
    Ok(())
}

// ---------------------------------------------------------------- user views

#[utoipa::path(
    get,
    path = "/support/",
    tag = "Support",
    summary = "List my support tickets",
    description = "Retrieve all support tickets belonging to the authenticated user, including message threads and attachments.",
    responses((status = 200, description = "Ticket list with count")),
    security(("bearer" = [])),
)]
pub async fn list_tickets(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let tickets: Vec<m::SupportTicket> = sqlx::query_as(
        "SELECT * FROM support_supportticket WHERE user_id = $1 ORDER BY created_at DESC",
    )
    .bind(user.id)
    .fetch_all(&s.db)
    .await?;
    let mut out = Vec::new();
    for t in &tickets {
        out.push(s::ticket_public(&s.db, t, &scheme, &host).await);
    }
    Ok((StatusCode::OK, Json(json!({"count": out.len(), "tickets": out}))))
}

#[utoipa::path(
    post,
    path = "/support/",
    tag = "Support",
    summary = "Create a support ticket",
    description = "Create a ticket. The description becomes the first message. Optional images attach to that message (multipart `images` fields).",
    responses((status = 201, description = "Ticket created"), (status = 400, description = "Invalid input")),
    security(("bearer" = [])),
)]
pub async fn create_ticket(
    State(s): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let form = parse_form(req, 20 * 1024 * 1024).await?;
    let subject = form.fields.get("subject").map(|v| v.trim().to_string()).unwrap_or_default();
    let description = form.fields.get("description").map(|v| v.trim().to_string()).unwrap_or_default();
    let priority = form.fields.get("priority").map(|v| v.trim().to_string()).unwrap_or_else(|| "medium".to_string());
    if subject.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"subject": ["This field is required."]}}))));
    }
    if description.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"description": ["This field is required."]}}))));
    }
    if !m::PRIORITIES.contains(&priority.as_str()) {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"priority": [format!("\"{priority}\" is not a valid choice.")]}}))));
    }
    let now = now_str();
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO support_supportticket (subject, description, status, priority, created_at, updated_at, user_id) VALUES ($1, $2, 'open', $3, $4, $5, $6) RETURNING id",
    )
    .bind(&subject)
    .bind(&description)
    .bind(&priority)
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(user.id)
    .fetch_one(&s.db)
    .await?;
    let ticket_id = res.0;
    let msg_res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO support_supportmessage (message, is_admin, created_at, sender_id, ticket_id) VALUES ($1, FALSE, $2, $3, $4) RETURNING id",
    )
    .bind(&description)
    .bind(crate::time::Ts(&now))
    .bind(user.id)
    .bind(ticket_id)
    .fetch_one(&s.db)
    .await?;
    let message_id = msg_res.0;
    if !form.images.is_empty() {
        save_images(&s.db, &s.config.media_root, message_id, &form.images, &now).await?;
    }
    let ticket = m::ticket_any(&s.db, ticket_id)
        .await?
        .ok_or_else(|| AppError::internal("Ticket not created"))?;
    let public = s::ticket_public(&s.db, &ticket, &scheme, &host).await;
    Ok((
        StatusCode::CREATED,
        Json(json!({"success": true, "message": "Support ticket created successfully", "ticket": public})),
    ))
}

#[utoipa::path(
    get,
    path = "/support/{ticket_id}/",
    tag = "Support",
    summary = "Get support ticket detail",
    params(("ticket_id" = i64, Path, description = "Ticket ID")),
    responses((status = 200, description = "Ticket detail"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn ticket_detail(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let Some(ticket) = m::ticket_owned(&s.db, ticket_id, user.id).await? else {
        return Ok(not_found());
    };
    let public = s::ticket_public(&s.db, &ticket, &scheme, &host).await;
    Ok((StatusCode::OK, Json(serde_json::to_value(&public).unwrap_or(Value::Null))))
}

#[utoipa::path(
    post,
    path = "/support/{ticket_id}/",
    tag = "Support",
    summary = "Add a message to a support ticket",
    params(("ticket_id" = i64, Path, description = "Ticket ID")),
    responses((status = 201, description = "Message added"), (status = 400, description = "Invalid input"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn add_message(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<i64>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let Some(ticket) = m::ticket_owned(&s.db, ticket_id, user.id).await? else {
        return Ok(not_found());
    };
    let form = parse_form(req, 20 * 1024 * 1024).await?;
    let text = form.fields.get("message").map(|v| v.trim().to_string()).unwrap_or_default();
    if text.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"message": ["This field is required."]}}))));
    }
    let now = now_str();
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO support_supportmessage (message, is_admin, created_at, sender_id, ticket_id) VALUES ($1, FALSE, $2, $3, $4) RETURNING id",
    )
    .bind(&text)
    .bind(crate::time::Ts(&now))
    .bind(user.id)
    .bind(ticket.id)
    .fetch_one(&s.db)
    .await?;
    let message_id = res.0;
    if !form.images.is_empty() {
        save_images(&s.db, &s.config.media_root, message_id, &form.images, &now).await?;
    }
    m::touch_ticket(&s.db, ticket.id, &now).await?;
    let row: m::SupportMessage = sqlx::query_as("SELECT * FROM support_supportmessage WHERE id = $1")
        .bind(message_id)
        .fetch_one(&s.db)
        .await?;
    let public = s::message_public(&s.db, &row, &scheme, &host).await;
    Ok((StatusCode::CREATED, Json(json!({"success": true, "message": public}))))
}

// ---------------------------------------------------------------- admin views

async fn require_admin(s: &AppState, headers: HeaderMap) -> Result<crate::accounts::models::Profile, Resp> {
    let user = auth_user(State(s.clone()), headers).await.map_err(|e| {
        (StatusCode::UNAUTHORIZED, Json(json!({"detail": e.message})))
    })?;
    if !user.is_admin {
        return Err(forbidden());
    }
    Ok(user)
}

#[utoipa::path(
    get,
    path = "/support/admin/tickets/",
    tag = "Support Admin",
    summary = "List all support tickets (admin)",
    params(
        ("status" = Option<String>, Query, description = "Filter by status"),
        ("priority" = Option<String>, Query, description = "Filter by priority"),
        ("search" = Option<String>, Query, description = "Search subject, description, user email/name"),
    ),
    responses((status = 200, description = "All tickets"), (status = 403, description = "Admin only")),
    security(("bearer" = [])),
)]
pub async fn admin_list(
    State(s): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let _admin = match require_admin(&s, headers.clone()).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let (scheme, host) = scheme_host(&headers);
    let mut sql = "SELECT t.* FROM support_supportticket t LEFT JOIN accounts_profile p ON p.id = t.user_id".to_string();
    let mut clauses: Vec<String> = Vec::new();
    let mut binds: Vec<String> = Vec::new();
    // PG placeholders are positional: number clauses in bind order.
    let mut next_idx = 1;
    let mut ph = || {
        let s = format!("${next_idx}");
        next_idx += 1;
        s
    };
    if let Some(st) = params.get("status").filter(|v| !v.is_empty()) {
        clauses.push(format!("t.status = {}", ph()));
        binds.push(st.clone());
    }
    if let Some(pr) = params.get("priority").filter(|v| !v.is_empty()) {
        clauses.push(format!("t.priority = {}", ph()));
        binds.push(pr.clone());
    }
    if let Some(q) = params.get("search").filter(|v| !v.is_empty()) {
        let like = format!("%{}%", q.replace('\\', "\\\\").replace('%', "\\%").replace('_', "\\_"));
        let ors: Vec<String> = ["t.subject", "t.description", "p.email", "p.surname", "p.other_names"]
            .iter()
            .map(|c| format!("{c} LIKE {} ESCAPE '\\'", ph()))
            .collect();
        clauses.push(format!("({})", ors.join(" OR ")));
        for _ in 0..5 {
            binds.push(like.clone());
        }
    }
    if !clauses.is_empty() {
        sql.push_str(&format!(" WHERE {}", clauses.join(" AND ")));
    }
    sql.push_str(" ORDER BY t.created_at DESC");
    let mut q = sqlx::query_as::<_, m::SupportTicket>(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    let tickets = q.fetch_all(&s.db).await?;
    let mut out = Vec::new();
    for t in &tickets {
        out.push(s::admin_ticket_public(&s.db, t, &scheme, &host).await);
    }
    Ok((StatusCode::OK, Json(json!({"tickets": out}))))
}

#[utoipa::path(
    get,
    path = "/support/admin/tickets/{ticket_id}/",
    tag = "Support Admin",
    summary = "Get support ticket detail (admin)",
    params(("ticket_id" = i64, Path, description = "Ticket ID")),
    responses((status = 200, description = "Ticket detail"), (status = 403, description = "Admin only"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn admin_detail(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<i64>,
) -> Result<Resp, AppError> {
    let _admin = match require_admin(&s, headers.clone()).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let (scheme, host) = scheme_host(&headers);
    let Some(ticket) = m::ticket_any(&s.db, ticket_id).await? else {
        return Ok(not_found());
    };
    let public = s::admin_ticket_public(&s.db, &ticket, &scheme, &host).await;
    Ok((StatusCode::OK, Json(serde_json::to_value(&public).unwrap_or(Value::Null))))
}

#[utoipa::path(
    patch,
    path = "/support/admin/tickets/{ticket_id}/",
    tag = "Support Admin",
    summary = "Update ticket status or priority (admin)",
    params(("ticket_id" = i64, Path, description = "Ticket ID")),
    responses((status = 200, description = "Updated"), (status = 400, description = "Invalid input"), (status = 403, description = "Admin only"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn admin_update(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<i64>,
    Json(body): Json<s::AdminUpdateBody>,
) -> Result<Resp, AppError> {
    let _admin = match require_admin(&s, headers.clone()).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let Some(mut ticket) = m::ticket_any(&s.db, ticket_id).await? else {
        return Ok(not_found());
    };
    let mut set: Vec<String> = Vec::new();
    // Binds below run status?, priority?, now, id — number SET params to match.
    let mut next_idx = 1i64;
    if let Some(st) = body.status.as_deref() {
        if !m::STATUSES.contains(&st) {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"status": [format!("\"{st}\" is not a valid choice.")]}}))));
        }
        ticket.status = st.to_string();
        set.push(format!("status = ${next_idx}"));
        next_idx += 1;
    }
    if let Some(pr) = body.priority.as_deref() {
        if !m::PRIORITIES.contains(&pr) {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"priority": [format!("\"{pr}\" is not a valid choice.")]}}))));
        }
        ticket.priority = pr.to_string();
        set.push(format!("priority = ${next_idx}"));
        next_idx += 1;
    }
    if set.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "Provide status and/or priority."}))));
    }
    let now = now_str();
    let ts_idx = next_idx;
    let id_idx = next_idx + 1;
    let sql = format!("UPDATE support_supportticket SET {}, updated_at = ${ts_idx} WHERE id = ${id_idx}", set.join(", "));
    let mut q = sqlx::query(&sql);
    if body.status.is_some() {
        q = q.bind(&ticket.status);
    }
    if body.priority.is_some() {
        q = q.bind(&ticket.priority);
    }
    q.bind(crate::time::Ts(&now)).bind(ticket.id).execute(&s.db).await?;
    s.support_hub.publish_ticket_event(ticket.id, ticket.user_id, &json!({
        "type": "ticket_update",
        "ticket_id": ticket.id,
        "status": ticket.status,
        "priority": ticket.priority,
    }));
    Ok((StatusCode::OK, Json(json!({"success": true, "status": ticket.status, "priority": ticket.priority}))))
}

#[utoipa::path(
    post,
    path = "/support/admin/tickets/{ticket_id}/reply/",
    tag = "Support Admin",
    summary = "Reply to a support ticket (admin)",
    params(("ticket_id" = i64, Path, description = "Ticket ID")),
    responses((status = 201, description = "Reply created"), (status = 400, description = "Invalid input"), (status = 403, description = "Admin only"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn admin_reply(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<i64>,
    req: Request,
) -> Result<Resp, AppError> {
    let admin = match require_admin(&s, headers.clone()).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let (scheme, host) = scheme_host(&headers);
    let Some(ticket) = m::ticket_any(&s.db, ticket_id).await? else {
        return Ok(not_found());
    };
    let form = parse_form(req, 20 * 1024 * 1024).await?;
    let text = form.fields.get("message").map(|v| v.trim().to_string()).unwrap_or_default();
    if text.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"message": ["This field is required."]}}))));
    }
    let now = now_str();
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO support_supportmessage (message, is_admin, created_at, sender_id, ticket_id) VALUES ($1, TRUE, $2, $3, $4) RETURNING id",
    )
    .bind(&text)
    .bind(crate::time::Ts(&now))
    .bind(admin.id)
    .bind(ticket.id)
    .fetch_one(&s.db)
    .await?;
    let message_id = res.0;
    if !form.images.is_empty() {
        save_images(&s.db, &s.config.media_root, message_id, &form.images, &now).await?;
    }
    let row: m::SupportMessage = sqlx::query_as("SELECT * FROM support_supportmessage WHERE id = $1")
        .bind(message_id)
        .fetch_one(&s.db)
        .await?;
    let public = s::message_public(&s.db, &row, &scheme, &host).await;
    s.support_hub.publish_ticket_event(ticket.id, ticket.user_id, &json!({
        "type": "new_message",
        "ticket_id": ticket.id,
        "message": public,
    }));
    Ok((StatusCode::CREATED, Json(json!({"success": true, "message": public}))))
}
