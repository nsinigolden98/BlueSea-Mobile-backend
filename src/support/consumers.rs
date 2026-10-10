//! Support live-chat websocket handlers.
//! Mirrors `support/consumers.py` + `support/routing.py`
//! (`ws/support/`, `ws/support/<ticket_id>/`):
//! JWT via `?token=` / `?access=` / `Authorization: Bearer`,
//! close 4401 unauthenticated, 4403 forbidden, 4404 unknown ticket,
//! `connected` snapshot on open, `ping` → `pong`, `send_message`,
//! `update_status` / `update_priority` (admin only), live fan-out through
//! `SupportHub` groups `support_ticket_<id>` / `support_user_<id>`.

use std::collections::HashMap;

use axum::{
    extract::{
        Path, Query, State,
        ws::{CloseFrame, Message, WebSocket, WebSocketUpgrade},
    },
    http::HeaderMap,
    response::IntoResponse,
};
use base64::Engine as _;
use serde_json::{Value, json};

use crate::auth::extractor::get_profile;
use crate::auth::jwt as auth_jwt;
use crate::state::AppState;
use crate::time::now_str;
use crate::transactions::serializers::format_created_at_lagos;

use super::models as m;

const ALLOWED_IMAGE_EXTS: &[&str] = &["png", "jpg", "jpeg", "webp", "gif"];
const MAX_IMAGE_BYTES: usize = 5 * 1024 * 1024;
const MAX_IMAGES_PER_MESSAGE: usize = 3;

struct Identity {
    user_id: i64,
    user_name: String,
    is_admin: bool,
}

async fn authed_identity(
    state: &AppState,
    params: &HashMap<String, String>,
    headers: &HeaderMap,
) -> Option<Identity> {
    let mut token = params
        .get("token")
        .or_else(|| params.get("access"))
        .cloned()
        .unwrap_or_default();
    if token.is_empty() {
        if let Some(h) = headers.get("authorization").and_then(|v| v.to_str().ok()) {
            if h.len() > 7 && h[..7].eq_ignore_ascii_case("bearer ") {
                token = h[7..].to_string();
            }
        }
    }
    if token.is_empty() {
        return None;
    }
    // Mirrors UntypedToken: any live signed token is accepted here.
    let claims = auth_jwt::decode_claims(&token, &state.config.secret_key).ok()?;
    if auth_jwt::is_blacklisted(&state.db, &claims.jti).await.ok()? {
        return None;
    }
    let user = get_profile(&state.db, claims.user_id).await.ok()?;
    if !user.is_active {
        return None;
    }
    Some(Identity {
        user_id: user.id,
        user_name: format!("{} {}", user.surname, user.other_names).trim().to_string(),
        is_admin: user.is_admin,
    })
}

fn decode_data_url_image(data_url: &str) -> Result<(Vec<u8>, String), String> {
    let Some((header, b64)) = data_url.split_once(";base64,") else {
        return Err("Image must be a data URL (data:image/<type>;base64,...).".to_string());
    };
    if !header.starts_with("data:image/") {
        return Err("Only image data URLs are allowed.".to_string());
    }
    let ext = header["data:image/".len()..].split(';').next().unwrap_or("").to_lowercase();
    if !ALLOWED_IMAGE_EXTS.contains(&ext.as_str()) {
        return Err(format!("Unsupported image type '{ext}'."));
    }
    let raw = base64::engine::general_purpose::STANDARD
        .decode(b64)
        .map_err(|_| "Invalid base64 image data.".to_string())?;
    if raw.is_empty() || raw.len() > MAX_IMAGE_BYTES {
        return Err(format!("Image must be non-empty and <= {}MB.", MAX_IMAGE_BYTES / (1024 * 1024)));
    }
    let ext = if ext == "jpeg" { "jpg".to_string() } else { ext };
    Ok((raw, ext))
}

async fn store_ws_upload(
    state: &AppState,
    raw: &[u8],
    ext: &str,
    now: &chrono::DateTime<chrono::Utc>,
) -> Option<String> {
    let dir = format!("support_attachments/{}", now.format("%Y/%m/%d"));
    let stored = format!("{dir}/{}.{ext}", uuid::Uuid::new_v4().simple());
    let path = std::path::Path::new(&state.config.media_root).join(&stored);
    if let Some(parent) = path.parent() {
        if tokio::fs::create_dir_all(parent).await.is_err() {
            return None;
        }
    }
    if tokio::fs::write(&path, raw).await.is_err() {
        return None;
    }
    Some(stored)
}

struct ChatCreated {
    owner_id: i64,
    payload: Value,
}

async fn create_chat_message(
    state: &AppState,
    ticket_id: i64,
    sender_id: i64,
    is_admin: bool,
    text: &str,
    image_data_urls: Vec<String>,
) -> Result<ChatCreated, String> {
    let Some(ticket) = m::ticket_any(&state.db, ticket_id).await.map_err(|e| e.to_string())? else {
        return Err("Ticket not found.".to_string());
    };
    if !is_admin && ticket.user_id != sender_id {
        return Err("Not allowed on this ticket.".to_string());
    }
    let text = text.trim().to_string();
    if text.is_empty() && image_data_urls.is_empty() {
        return Err("Message text or images required.".to_string());
    }
    if image_data_urls.len() > MAX_IMAGES_PER_MESSAGE {
        return Err(format!("Max {MAX_IMAGES_PER_MESSAGE} images per message."));
    }
    let mut files: Vec<(Vec<u8>, String)> = Vec::new();
    for data_url in &image_data_urls {
        files.push(decode_data_url_image(data_url)?);
    }
    let sender = get_profile(&state.db, sender_id).await.map_err(|_| "Sender not found.".to_string())?;
    let now = now_str();
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO support_supportmessage (message, is_admin, created_at, sender_id, ticket_id) VALUES ($1, $2, $3, $4, $5) RETURNING id",
    )
    .bind(&text)
    .bind(is_admin)
    .bind(crate::time::Ts(&now))
    .bind(sender_id)
    .bind(ticket_id)
    .fetch_one(&state.db)
    .await
    .map_err(|e| e.to_string())?;
    let message_id = res.0;
    let now_dt = chrono::Utc::now();
    let mut attachments = Vec::new();
    for (raw, ext) in &files {
        let Some(stored) = store_ws_upload(state, raw, ext, &now_dt).await else {
            return Err("Could not store image.".to_string());
        };
        let att = sqlx::query_as::<_, (i64,)>("INSERT INTO support_supportattachment (image, uploaded_at, message_id) VALUES ($1, $2, $3) RETURNING id")
            .bind(&stored)
            .bind(crate::time::Ts(&now))
            .bind(message_id)
            .fetch_one(&state.db)
            .await
            .map_err(|e| e.to_string())?;
        attachments.push(json!({"id": att.0, "image": format!("/media/{stored}")}));
    }
    m::touch_ticket(&state.db, ticket_id, &now).await.map_err(|e| e.to_string())?;
    Ok(ChatCreated {
        owner_id: ticket.user_id,
        payload: json!({
            "type": "new_message",
            "ticket_id": ticket_id,
            "message": {
                "id": message_id,
                "sender_id": sender_id,
                "sender_name": format!("{} {}", sender.surname, sender.other_names).trim().to_string(),
                "message": text,
                "is_admin": is_admin,
                "attachments": attachments,
                "created_at": format_created_at_lagos(&now),
            },
        }),
    })
}

async fn update_ticket_field(
    state: &AppState,
    ticket_id: i64,
    is_admin: bool,
    field: &str,
    value: &str,
) -> Result<(i64, Value), String> {
    if !is_admin {
        return Err("Admin only.".to_string());
    }
    let (valid, event_type) = if field == "status" {
        (m::STATUSES, "status_update")
    } else {
        (m::PRIORITIES, "priority_update")
    };
    if !valid.contains(&value) {
        return Err(format!("Invalid {field} '{value}'."));
    }
    let Some(_) = m::ticket_any(&state.db, ticket_id).await.map_err(|e| e.to_string())? else {
        return Err("Ticket not found.".to_string());
    };
    let now = now_str();
    let sql = format!("UPDATE support_supportticket SET {field} = $1, updated_at = $2 WHERE id = $3");
    sqlx::query(&sql).bind(value).bind(crate::time::Ts(&now)).bind(ticket_id).execute(&state.db).await.map_err(|e| e.to_string())?;
    let ticket = m::ticket_any(&state.db, ticket_id).await.map_err(|e| e.to_string())?.unwrap();
    Ok((ticket.user_id, json!({"type": event_type, "ticket_id": ticket_id, field: value})))
}

async fn send_error(socket: &mut WebSocket, detail: &str) {
    let _ = socket.send(Message::Text(json!({"type": "error", "detail": detail}).to_string().into())).await;
}

fn resolve_ticket_id(data: &Value, scoped: Option<i64>) -> Result<Option<i64>, ()> {
    match data.get("ticket_id") {
        Some(raw) => {
            if let Some(n) = raw.as_i64() {
                Ok(Some(n))
            } else if let Some(s) = raw.as_str() {
                s.trim().parse::<i64>().map(Some).map_err(|_| ())
            } else if let Some(n) = raw.as_u64().and_then(|v| i64::try_from(v).ok()) {
                Ok(Some(n))
            } else {
                Err(())
            }
        }
        None => Ok(scoped),
    }
}

async fn on_send_message(state: &AppState, socket: &mut WebSocket, id: &Identity, scoped: Option<i64>, data: &Value) {
    let ticket_id = match resolve_ticket_id(data, scoped) {
        Ok(Some(t)) => t,
        Ok(None) => {
            send_error(socket, "ticket_id is required.").await;
            return;
        }
        Err(_) => {
            send_error(socket, "Invalid ticket_id.").await;
            return;
        }
    };
    if scoped.is_some_and(|s| s != ticket_id) {
        send_error(socket, "ticket_id does not match this connection.").await;
        return;
    }
    let images = match data.get("images") {
        None | Some(Value::Null) => Vec::new(),
        Some(Value::Array(items)) => {
            let mut out = Vec::new();
            for item in items {
                match item.as_str() {
                    Some(s) => out.push(s.to_string()),
                    None => {
                        send_error(socket, "images must be an array of data URLs.").await;
                        return;
                    }
                }
            }
            out
        }
        _ => {
            send_error(socket, "images must be an array of data URLs.").await;
            return;
        }
    };
    let text = data.get("message").and_then(|v| v.as_str()).unwrap_or("");
    match create_chat_message(state, ticket_id, id.user_id, id.is_admin, text, images).await {
        Ok(created) => {
            state.support_hub.publish_ticket_event(ticket_id, created.owner_id, &created.payload);
        }
        Err(detail) => send_error(socket, &detail).await,
    }
}

async fn on_update_field(state: &AppState, socket: &mut WebSocket, id: &Identity, scoped: Option<i64>, data: &Value, field: &str) {
    if !id.is_admin {
        send_error(socket, "Admin only.").await;
        return;
    }
    let ticket_id = match resolve_ticket_id(data, scoped) {
        Ok(Some(t)) => t,
        Ok(None) => {
            send_error(socket, "ticket_id is required.").await;
            return;
        }
        Err(_) => {
            send_error(socket, "Invalid ticket_id.").await;
            return;
        }
    };
    if scoped.is_some_and(|s| s != ticket_id) {
        send_error(socket, "ticket_id does not match this connection.").await;
        return;
    }
    let value = data.get(field).and_then(|v| v.as_str()).unwrap_or("");
    match update_ticket_field(state, ticket_id, true, field, value).await {
        Ok((owner_id, payload)) => {
            state.support_hub.publish_ticket_event(ticket_id, owner_id, &payload);
        }
        Err(detail) => send_error(socket, &detail).await,
    }
}

async fn close_with(socket: WebSocket, code: u16) {
    let mut socket = socket;
    let _ = socket
        .send(Message::Close(Some(CloseFrame { code, reason: "".into() })))
        .await;
}

async fn handle_socket(mut socket: WebSocket, state: AppState, id: Identity, scoped: Option<i64>, owner_id: Option<i64>) {
    let mut groups = vec![format!("support_user_{}", id.user_id)];
    if let Some(tid) = scoped {
        groups.push(format!("support_ticket_{tid}"));
        if id.is_admin {
            if let Some(owner) = owner_id {
                let g = format!("support_user_{owner}");
                if !groups.contains(&g) {
                    groups.push(g);
                }
            }
        }
    }
    // One forwarder per group into a single channel the socket loop selects on.
    let (tx, mut inbox) = tokio::sync::mpsc::unbounded_channel::<String>();
    for group in &groups {
        let mut rx = state.support_hub.subscribe(group);
        let tx = tx.clone();
        tokio::spawn(async move {
            loop {
                match rx.recv().await {
                    Ok(text) => {
                        if tx.send(text).is_err() {
                            break;
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                }
            }
        });
    }
    drop(tx);

    let hello = json!({
        "type": "connected",
        "user_id": id.user_id,
        "user_name": id.user_name,
        "is_admin": id.is_admin,
        "ticket_id": scoped,
    });
    if socket.send(Message::Text(hello.to_string().into())).await.is_err() {
        return;
    }

    loop {
        tokio::select! {
            msg = socket.recv() => {
                let Some(Ok(msg)) = msg else { break };
                let Message::Text(text) = msg else { continue };
                let data: Value = match serde_json::from_str(text.as_str()) {
                    Ok(v) => v,
                    Err(_) => {
                        send_error(&mut socket, "Invalid JSON.").await;
                        continue;
                    }
                };
                if !data.is_object() {
                    send_error(&mut socket, "Invalid payload.").await;
                    continue;
                }
                match data.get("type").and_then(|t| t.as_str()) {
                    Some("ping") => {
                        if socket.send(Message::Text(json!({"type": "pong"}).to_string().into())).await.is_err() {
                            break;
                        }
                    }
                    Some("send_message") => on_send_message(&state, &mut socket, &id, scoped, &data).await,
                    Some("update_status") => on_update_field(&state, &mut socket, &id, scoped, &data, "status").await,
                    Some("update_priority") => on_update_field(&state, &mut socket, &id, scoped, &data, "priority").await,
                    other => {
                        let detail = format!("Unknown type '{}'.", other.unwrap_or("null"));
                        send_error(&mut socket, &detail).await;
                    }
                }
            }
            forwarded = inbox.recv() => {
                match forwarded {
                    Some(text) => {
                        if socket.send(Message::Text(text.into())).await.is_err() {
                            break;
                        }
                    }
                    None => break,
                }
            }
        }
    }
}

async fn accept_or_close(
    ws: WebSocketUpgrade,
    params: HashMap<String, String>,
    headers: HeaderMap,
    state: AppState,
    scoped: Option<i64>,
) -> impl IntoResponse {
    let Some(id) = authed_identity(&state, &params, &headers).await else {
        return ws.on_upgrade(|socket| async move { close_with(socket, 4401).await });
    };
    if let Some(tid) = scoped {
        let access = sqlx::query_as::<_, (i64,)>("SELECT user_id FROM support_supportticket WHERE id = $1")
            .bind(tid)
            .fetch_optional(&state.db)
            .await
            .ok()
            .flatten();
        let Some((owner_id,)) = access else {
            return ws.on_upgrade(|socket| async move { close_with(socket, 4404).await });
        };
        if !id.is_admin && owner_id != id.user_id {
            return ws.on_upgrade(|socket| async move { close_with(socket, 4403).await });
        }
        let state = state.clone();
        return ws.on_upgrade(move |socket| async move {
            handle_socket(socket, state, id, Some(tid), Some(owner_id)).await;
        });
    }
    ws.on_upgrade(move |socket| async move {
        handle_socket(socket, state, id, None, None).await;
    })
}

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    Query(params): Query<HashMap<String, String>>,
    headers: HeaderMap,
    State(state): State<AppState>,
) -> impl IntoResponse {
    accept_or_close(ws, params, headers, state, None).await
}

pub async fn ws_handler_ticket(
    ws: WebSocketUpgrade,
    Path(ticket_id): Path<i64>,
    Query(params): Query<HashMap<String, String>>,
    headers: HeaderMap,
    State(state): State<AppState>,
) -> impl IntoResponse {
    accept_or_close(ws, params, headers, state, Some(ticket_id)).await
}
