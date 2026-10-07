//! Route table for affiliates. Mirrors `affiliate/urls.py`
//! (mounted at `/affiliate/`).

use axum::{Router, routing::{get, post}};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/affiliate/apply/", post(views::apply))
        .route("/affiliate/status/", get(views::status))
        .route(
            "/affiliate/links/",
            get(views::links_list).post(views::links_create),
        )
        .route("/affiliate/attribution/", post(views::attribution))
        .route("/affiliate/dashboard/", get(views::dashboard))
        .route("/affiliate/sales/", get(views::sales))
        .route("/affiliate/payout/", post(views::payout))
        .with_state(state)
}
