//! Route table for the transactions app. Mirrors `transactions/urls.py`.

use axum::{Router, routing::{get, post}};

use crate::state::AppState;

use super::nomba_views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/transactions/history/", get(crate::transactions::views::history::history))
        .route(
            "/transactions/nomba/fund-wallet/",
            post(nomba_views::initialize_funding),
        )
        .route(
            "/transactions/nomba/account-name/",
            post(nomba_views::account_name),
        )
        .route(
            "/transactions/nomba/dva/assign/",
            post(nomba_views::dva_assign),
        )
        .route(
            "/transactions/nomba/dva/confirm/",
            post(nomba_views::dva_confirm),
        )
        .route("/transactions/nomba/webhook/", post(nomba_views::webhook))
        .with_state(state)
}
