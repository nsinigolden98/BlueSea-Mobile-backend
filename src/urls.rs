//! Top-level route table.
//! Mirrors `bluesea_mobile/urls.py` — mounts each app's `urls.rs`
//! (plus websocket `routing.rs` tables).

use axum::Router;

use crate::state::AppState;

pub fn router(state: AppState) -> Router {
    Router::new()
        .merge(crate::accounts::urls::router(state.clone()))
        .merge(crate::wallet::urls::router(state.clone()))
        .merge(crate::wallet::routing::router(state))
        .route("/health", axum::routing::get(|| async { "ok" }))
}
