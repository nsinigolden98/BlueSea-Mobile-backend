//! Websocket route table for the support app. Mirrors `support/routing.py`.

use axum::{Router, routing::get};

use crate::state::AppState;

use super::consumers;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/ws/support/", get(consumers::ws_handler))
        .route("/ws/support/{ticket_id}/", get(consumers::ws_handler_ticket))
        .with_state(state)
}
