//! Top-level route table.
//! Mirrors `bluesea_mobile/urls.py` — mounts each app's `urls.rs`
//! (plus websocket `routing.rs` tables) and the API docs
//! (`/schema/`, `/docs/`, `/redoc/`, like drf-spectacular).

use axum::{Json, Router, routing::get};
use utoipa::OpenApi;
use utoipa_redoc::{Redoc, Servable as _};
use utoipa_swagger_ui::SwaggerUi;

use crate::state::AppState;

pub fn router(state: AppState) -> Router {
    Router::new()
        .merge(crate::accounts::urls::router(state.clone()))
        .merge(crate::wallet::urls::router(state.clone()))
        .merge(crate::wallet::routing::router(state.clone()))
        .merge(crate::transactions::urls::router(state.clone()))
        .merge(crate::payments::urls::router(state))
        .route("/health", get(|| async { "ok" }))
        .route(
            "/schema/",
            get(|| async { Json(crate::docs::ApiDoc::openapi()) }),
        )
        .merge(
            SwaggerUi::new("/docs")
                .url("/schema/openapi.json", crate::docs::ApiDoc::openapi()),
        )
        .merge(Redoc::with_url("/redoc", crate::docs::ApiDoc::openapi()))
}
