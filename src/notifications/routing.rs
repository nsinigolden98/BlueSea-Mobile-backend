//! Websocket route table for the notifications app.

use axum::{Router, routing::get};

use crate::state::AppState;

use super::consumers;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/ws/notifications/", get(consumers::ws_handler))
        .with_state(state)
}
