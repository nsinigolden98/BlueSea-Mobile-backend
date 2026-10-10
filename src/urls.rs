//! Top-level route table.
//! Mirrors `bluesea_mobile/urls.py` — mounts each app's `urls.rs`
//! (plus websocket `routing.rs` tables) and the API docs
//! (`/schema/`, `/docs/`, `/redoc/`, like drf-spectacular).

use axum::{Json, Router, routing::get};
use tower_http::services::ServeDir;
use utoipa::OpenApi;
use utoipa_redoc::{Redoc, Servable as _};
use utoipa_swagger_ui::SwaggerUi;

use crate::state::AppState;

pub fn router(state: AppState) -> Router {
    let media_root = state.config.media_root.clone();
    Router::new()
        .merge(crate::accounts::urls::router(state.clone()))// accounts
        .merge(crate::wallet::urls::router(state.clone()))// wallet
        .merge(crate::wallet::routing::router(state.clone()))// wallet websockets
        .merge(crate::plans_cache::router(state.clone()))// plans websocket
        .merge(crate::transactions::urls::router(state.clone()))// transactions
        .merge(crate::payments::urls::router(state.clone()))// payments
        .merge(crate::user_preference::urls::router(state.clone()))// user-preference
        .merge(crate::notifications::urls::router(state.clone()))// notifications
        .merge(crate::notifications::routing::router(state.clone()))// notifications websockets
        .merge(crate::bonus::urls::router(state.clone()))// bonus
        .merge(crate::autotopup::urls::router(state.clone()))// autotopup
        .merge(crate::loyalty_market::urls::router(state.clone())) //loyalty-market
        .merge(crate::group_payment::urls::router(state.clone()))// group-payment
        .merge(crate::affiliate::urls::router(state.clone())) //affiliate
        .merge(crate::support::urls::router(state.clone())) //support
        .merge(crate::support::routing::router(state.clone())) //support websockets
        .merge(crate::broadcast::urls::router(state.clone())) //broadcast
        .merge(crate::market_place::urls::router(state.clone())) //marketplace
        .merge(crate::admin::router(state.clone())) //staff admin JSON API
        .nest_service("/media/", ServeDir::new(media_root))// media files
        .route("/health", get(|| async { "ok" }))// health check
        .route(
            "/schema/",
            get(|| async { Json(crate::docs::ApiDoc::openapi()) }),
        )// OpenAPI schema
        .merge(
            SwaggerUi::new("/docs")
                .url("/schema/openapi.json", crate::docs::ApiDoc::openapi()),
        )// Swagger UI
        .merge(Redoc::with_url("/redoc", crate::docs::ApiDoc::openapi()))// ReDoc UI
        .fallback(crate::admin::spa_fallback)// React panel under /admin
}
