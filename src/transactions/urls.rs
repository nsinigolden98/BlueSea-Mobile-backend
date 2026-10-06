//! Route table for the transactions app. Mirrors `transactions/urls.py`.

use axum::{Router, routing::{get, post}};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/transactions/history/", get(views::history::history))
        .route(
            "/transactions/fund-wallet/",
            post(views::funding::initialize_funding),
        )
        .route(
            "/transactions/webhook/paystack/",
            post(views::webhook::paystack_webhook),
        )
        .route(
            "/transactions/account-name/",
            post(views::account_name::account_name),
        )
        .route(
            "/transactions/dva/refresh/",
            post(views::dva_refresh::dva_refresh),
        )
        .with_state(state)
}
