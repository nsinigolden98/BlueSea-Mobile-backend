//! Top-level route table.
//! Mirrors `bluesea_mobile/urls.py` — mounts each app's `urls.rs`
//! (plus websocket `routing.rs` tables) and the API docs
//! (`/schema/`, `/docs/`, `/redoc/`, like drf-spectacular).

use axum::{
    Json, Router,
    body::Body,
    extract::State,
    http::{HeaderMap, HeaderValue, Method, Request, StatusCode, header::LOCATION},
    middleware::{Next, from_fn, from_fn_with_state},
    response::{IntoResponse, Response},
    routing::get,
};
use tower_http::cors::{AllowOrigin, Any, CorsLayer};
use tower_http::services::ServeDir;
use utoipa::OpenApi;
use utoipa_redoc::{Redoc, Servable as _};
use utoipa_swagger_ui::SwaggerUi;

use crate::state::AppState;

/// CORS layer from env, mirroring Django's `django-cors-headers` setup
/// (`CORS_ALLOW_ALL_ORIGINS = DEBUG`, allowlist from `CORS_ALLOWED_ORIGINS`).
/// Methods match Django's `CORS_ALLOW_METHODS` default; headers are `Any`
/// (superset of Django's default list — safe for multipart/API clients).
/// Returns `None` when locked down to nothing (allow-all off, empty list),
/// exactly like Django answering with no CORS headers.
pub fn cors_layer(cors_allow_all: bool, cors_allowed_origins: &[String]) -> Option<CorsLayer> {
    if cors_allow_all {
        return Some(CorsLayer::permissive());
    }
    let origins: Vec<HeaderValue> = cors_allowed_origins
        .iter()
        .filter_map(|o| match o.parse::<HeaderValue>() {
            Ok(v) => Some(v),
            Err(e) => {
                tracing::warn!("ignoring bad CORS_ALLOWED_ORIGINS entry {o:?}: {e}");
                None
            }
        })
        .collect();
    if origins.is_empty() {
        return None;
    }
    Some(
        CorsLayer::new()
            .allow_origin(AllowOrigin::list(origins))
            .allow_methods([
                Method::GET,
                Method::POST,
                Method::PATCH,
                Method::PUT,
                Method::DELETE,
                Method::OPTIONS,
            ])
            .allow_headers(Any),
    )
}

/// App-level http→https redirect, mirroring Django's `SECURE_SSL_REDIRECT`
/// with `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
/// Requests nginx already served over TLS carry `X-Forwarded-Proto: https`
/// and pass through; direct plain-http hits (no proxy header) get a 301 to
/// the same host+path. No `is_secure`/scheme sniffing beyond the proxy
/// header — same trust model as Django behind nginx.
async fn ssl_redirect_mw(req: Request<Body>, next: Next) -> Response {
    let forwarded_https = req
        .headers()
        .get("x-forwarded-proto")
        .and_then(|v| v.to_str().ok())
        == Some("https");
    if forwarded_https {
        return next.run(req).await;
    }
    let Some(host) = req.headers().get("host").and_then(|v| v.to_str().ok()) else {
        return next.run(req).await;
    };
    let path = req.uri().path_and_query().map(|pq| pq.as_str()).unwrap_or("/");
    let location = format!("https://{host}{path}");
    Response::builder()
        .status(StatusCode::MOVED_PERMANENTLY)
        .header(LOCATION, location)
        .body(Body::from("HTTPS required"))
        .unwrap()
}

/// Superuser-only gate for API docs (`/schema/`, `/docs`, `/redoc`).
/// Reuses the admin login session: same `Bearer` JWT + `is_superuser` check
/// as `/admin/api/*`. Anon -> 401, non-superuser -> 403.
async fn require_superuser_mw(
    State(s): State<AppState>,
    headers: HeaderMap,
    req: Request<Body>,
    next: Next,
) -> Response {
    match crate::admin::require_staff(&s, headers).await {
        Ok(_) => next.run(req).await,
        Err((status, body)) => (status, body).into_response(),
    }
}

pub fn router(state: AppState) -> Router {
    let media_root = state.config.media_root.clone();
    let docs_router = Router::new()
        .route(
            "/schema/",
            get(|| async { Json(crate::docs::ApiDoc::openapi()) }),
        )
        .merge(
            SwaggerUi::new("/docs")
                .url("/schema/openapi.json", crate::docs::ApiDoc::openapi()),
        )
        .merge(Redoc::with_url("/redoc", crate::docs::ApiDoc::openapi()))
        .layer(from_fn_with_state(state.clone(), require_superuser_mw))
        .with_state(state.clone());
    let router = Router::new()
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
        .merge(docs_router)// superuser-only OpenAPI schema/docs/redoc
        .fallback(crate::admin::spa_fallback);// React panel under /admin
    // Outermost last: plain-http hits redirect before CORS runs (browsers
    // never send preflights over http in prod — nginx only proxies 443).
    let router = match cors_layer(
        state.config.cors_allow_all,
        &state.config.cors_allowed_origins,
    ) {
        Some(layer) => router.layer(layer),
        None => router,
    };
    if state.config.secure_ssl_redirect {
        router.layer(from_fn(ssl_redirect_mw))
    } else {
        router
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use tower::ServiceExt;

    fn app_with(layer: Option<CorsLayer>) -> Router {
        let base = Router::new().route("/health", get(|| async { "ok" }));
        match layer {
            Some(l) => base.layer(l),
            None => base,
        }
    }

    async fn get_with_origin(app: Router, origin: &str) -> (StatusCode, axum::http::HeaderMap) {
        let res = app
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .header("origin", origin)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        (res.status(), res.headers().clone())
    }

    #[tokio::test]
    async fn allowlisted_origin_gets_cors_headers() {
        let origins = ["https://blueseamobile.com".to_string()];
        let (status, headers) = get_with_origin(
            app_with(cors_layer(false, &origins)),
            "https://blueseamobile.com",
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            headers.get("access-control-allow-origin").unwrap(),
            "https://blueseamobile.com"
        );
    }

    #[tokio::test]
    async fn unknown_origin_gets_no_cors_headers() {
        let origins = ["https://blueseamobile.com".to_string()];
        let (status, headers) =
            get_with_origin(app_with(cors_layer(false, &origins)), "https://evil.test").await;
        assert_eq!(status, StatusCode::OK);
        assert!(headers.get("access-control-allow-origin").is_none());
    }

    #[tokio::test]
    async fn allow_all_returns_wildcard() {
        let (status, headers) =
            get_with_origin(app_with(cors_layer(true, &[])), "https://anything.test").await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(headers.get("access-control-allow-origin").unwrap(), "*");
    }

    #[tokio::test]
    async fn locked_down_means_no_layer() {
        assert!(cors_layer(false, &[]).is_none());
        let (status, headers) =
            get_with_origin(app_with(cors_layer(false, &[])), "https://blueseamobile.com").await;
        assert_eq!(status, StatusCode::OK);
        assert!(headers.get("access-control-allow-origin").is_none());
    }

    #[test]
    fn bad_origin_entries_are_skipped() {
        let origins = ["not a valid origin \u{7f}".to_string()];
        assert!(cors_layer(false, &origins).is_none());
    }

    #[tokio::test]
    async fn plain_http_redirects_to_https() {
        let app = Router::new()
            .route("/x", get(|| async { "ok" }))
            .layer(from_fn(ssl_redirect_mw));
        let res = app
            .oneshot(
                Request::builder()
                    .uri("/x?q=1")
                    .header("host", "api.blueseamobile.com")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::MOVED_PERMANENTLY);
        assert_eq!(
            res.headers().get("location").unwrap(),
            "https://api.blueseamobile.com/x?q=1"
        );
    }

    #[tokio::test]
    async fn forwarded_https_passes_through() {
        let app = Router::new()
            .route("/health", get(|| async { "ok" }))
            .layer(from_fn(ssl_redirect_mw));
        let res = app
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .header("host", "api.blueseamobile.com")
                    .header("x-forwarded-proto", "https")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::OK);
        assert!(res.headers().get("location").is_none());
    }
}
