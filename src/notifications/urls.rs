//! Route table for notifications. Mirrors `notifications/urls.py`.

use axum::{Router, routing::{delete, get, post}};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/notifications/", get(views::list))
        .route(
            "/notifications/{notification_id}/read/",
            post(views::mark_read),
        )
        .route("/notifications/mark-all-read/", post(views::mark_all_read))
        .route(
            "/notifications/{notification_id}/delete/",
            delete(views::delete),
        )
        .with_state(state)
}
