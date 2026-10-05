//! Websocket route table for the wallet app. Mirrors `wallet/routing.py`.

use axum::{Router, routing::get};

use crate::state::AppState;

use super::consumers;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/ws/wallet/", get(consumers::ws_handler))
        .route("/ws/wallet/balance/", get(consumers::ws_handler))
        .with_state(state)
}
