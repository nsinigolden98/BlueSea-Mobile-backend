//! REST route table for the wallet app. Mirrors `wallet/urls.py`.

use axum::{Router, routing::get};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/wallet/balance/", get(views::balance))
        .with_state(state)
}
