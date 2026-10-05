//! Wallet websocket handlers. Mirrors `wallet/consumers.py` +
//! `wallet/routing.py` (`ws/wallet/`, `ws/wallet/balance/`):
//! JWT via `?token=` / `?access=` / `Authorization: Bearer`,
//! close code 4401 when unauthenticated, `connected` snapshot on open,
//! `ping` → `pong`, `balance_request` → `balance_update`, and live
//! `balance_update` pushes on every credit/debit.

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

use super::models::{WalletBalances, get_by_user, parse_cents};

fn snapshot(db_balance: &str, db_locked: &str) -> WalletBalances {
    let b = parse_cents(db_balance).unwrap_or(0);
    let l = parse_cents(db_locked).unwrap_or(0);
    WalletBalances::from_cents(b, l)
}

async fn balances_for(state: &AppState, user_id: i64) -> WalletBalances {
    match get_by_user(&state.db, user_id).await.ok().flatten() {
        Some(w) => snapshot(&w.balance, &w.locked_balance),
        None => WalletBalances::from_cents(0, 0),
    }
}

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
    // Mirrors UntypedToken: any live signed token is accepted here.
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
    let mut rx = state.wallet_hub.subscribe(user_id);

    let balances = balances_for(&state, user_id).await;
    let hello = json!({
        "type": "connected",
        "user_id": user_id,
        "balance": balances.balance,
        "balance_formatted": balances.balance_formatted,
        "locked_balance": balances.locked_balance,
        "locked_balance_formatted": balances.locked_balance_formatted,
        "available_balance": balances.available_balance,
        "available_balance_formatted": balances.available_balance_formatted,
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
                    Some("balance_request") => {
                        let b = balances_for(&state, user_id).await;
                        let out = json!({
                            "type": "balance_update",
                            "balance": b.balance,
                            "balance_formatted": b.balance_formatted,
                            "locked_balance": b.locked_balance,
                            "locked_balance_formatted": b.locked_balance_formatted,
                            "available_balance": b.available_balance,
                            "available_balance_formatted": b.available_balance_formatted,
                        });
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
