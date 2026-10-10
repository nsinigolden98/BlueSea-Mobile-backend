//! Route table for broadcast. Mirrors `broadcast/urls.py`
//! (mounted at `/broadcast/`).

use axum::{Router, routing::get};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/broadcast/new-month/", get(views::new_month))
        .route("/broadcast/important/", get(views::important))
        .route("/broadcast/announcement/", get(views::announcement))
        .route("/broadcast/", get(views::history))
        .with_state(state)
}
