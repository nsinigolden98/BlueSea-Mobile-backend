use axum::{Json, http::StatusCode, response::{IntoResponse, Response}};
use serde_json::json;

#[derive(Debug)]
pub struct AppError {
    pub status: StatusCode,
    pub message: String,
}

impl AppError {
    pub fn new(status: StatusCode, message: impl Into<String>) -> Self {
        Self { status, message: message.into() }
    }
    pub fn bad_request(msg: impl Into<String>) -> Self { Self::new(StatusCode::BAD_REQUEST, msg) }
    pub fn unauthorized(msg: impl Into<String>) -> Self { Self::new(StatusCode::UNAUTHORIZED, msg) }
    pub fn not_found(msg: impl Into<String>) -> Self { Self::new(StatusCode::NOT_FOUND, msg) }
    pub fn too_many(msg: impl Into<String>) -> Self { Self::new(StatusCode::TOO_MANY_REQUESTS, msg) }
    pub fn internal(msg: impl Into<String>) -> Self { Self::new(StatusCode::INTERNAL_SERVER_ERROR, msg) }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let body = Json(json!({ "message": self.message, "state": false }));
        (self.status, body).into_response()
    }
}

impl From<sqlx::Error> for AppError {
    fn from(e: sqlx::Error) -> Self {
        tracing::error!("db error: {e}");
        Self::internal("Database error")
    }
}

impl From<jsonwebtoken::errors::Error> for AppError {
    fn from(e: jsonwebtoken::errors::Error) -> Self {
        Self::unauthorized(format!("Token error: {e}"))
    }
}
