//! Notification websocket handler (`ws/notifications/`):
//! JWT via `?token=` / `?access=` / `Authorization: Bearer` (same helper
//! semantics as the wallet socket), close code 4401 when unauthenticated,
//! `connected` snapshot with `unread_count` on open, `ping` → `pong`, and
//! live `new_notification` pushes for every stored row.

use std::collections::HashMap;

use axum::{
    extract::{
        Query, State,
        ws::{CloseFrame, Message, WebSocket, WebSocketUpgrade},
    },
    http::HeaderMap,
    response::IntoResponse,
};
use serde_json::json;

use crate::auth::extractor::get_profile;
use crate::auth::jwt as auth_jwt;
use crate::state::AppState;

async fn authed_user_id(state: &AppState, params: &HashMap<String, String>, headers: &HeaderMap) -> Option<i64> {
    let mut token = params
        .get("token")
        .or_else(|| params.get("access"))
        .cloned()
        .unwrap_or_default();
    if token.is_empty() {
        if let Some(h) = headers
            .get("authorization")
            .and_then(|v| v.to_str().ok())
        {
            if h.len() > 7 && h[..7].eq_ignore_ascii_case("bearer ") {
                token = h[7..].to_string();
            }
        }
    }
    if token.is_empty() {
        return None;
    }
    let claims = auth_jwt::decode_claims(&token, &state.config.secret_key).ok()?;
    if auth_jwt::is_blacklisted(&state.db, &claims.jti).await.ok()? {
        return None;
    }
    let user = get_profile(&state.db, claims.user_id).await.ok()?;
    if !user.is_active {
        return None;
    }
    Some(user.id)
}

async fn unread_count(state: &AppState, user_id: i64) -> i64 {
    sqlx::query_as::<_, (i64,)>(
        "SELECT COUNT(*) FROM notifications_notification WHERE user_id = $1 AND is_read = FALSE",
    )
    .bind(user_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten()
    .map(|r| r.0)
    .unwrap_or(0)
}

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    Query(params): Query<HashMap<String, String>>,
    headers: HeaderMap,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let user_id = authed_user_id(&state, &params, &headers).await;
    ws.on_upgrade(move |socket| handle_socket(socket, state, user_id))
}

async fn close_unauthorized(mut socket: WebSocket) {
    let _ = socket
        .send(Message::Close(Some(CloseFrame {
            code: 4401,
            reason: "unauthorized".into(),
        })))
        .await;
}

async fn handle_socket(mut socket: WebSocket, state: AppState, user_id: Option<i64>) {
    let Some(user_id) = user_id else {
        close_unauthorized(socket).await;
        return;
    };
    let mut rx = state.notification_hub.subscribe(user_id);

    let unread = unread_count(&state, user_id).await;
    let hello = json!({
        "type": "connected",
        "user_id": user_id,
        "unread_count": unread,
    });
    if socket
        .send(Message::Text(hello.to_string().into()))
        .await
        .is_err()
    {
        return;
    }

    loop {
        tokio::select! {
            msg = socket.recv() => {
                let Some(Ok(msg)) = msg else { break };
                let Message::Text(text) = msg else { continue };
                let value: serde_json::Value = match serde_json::from_str(text.as_str()) {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                match value.get("type").and_then(|t| t.as_str()) {
                    Some("ping") => {
                        if socket.send(Message::Text(json!({"type": "pong"}).to_string().into())).await.is_err() {
                            break;
                        }
                    }
                    Some("unread_request") => {
                        let n = unread_count(&state, user_id).await;
                        let out = json!({"type": "unread_update", "unread_count": n});
                        if socket.send(Message::Text(out.to_string().into())).await.is_err() {
                            break;
                        }
                    }
                    _ => {}
                }
            }
            update = rx.recv() => {
                match update {
                    Ok(text) => {
                        if socket.send(Message::Text(text.into())).await.is_err() {
                            break;
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
        }
    }
}
