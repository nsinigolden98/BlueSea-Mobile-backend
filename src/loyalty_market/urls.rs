//! Route table for the loyalty market. Mirrors `loyalty_market/urls.py`
//! (mounted at `/loyalty/`).

use axum::{Router, routing::{get, post}};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/loyalty/rewards/", get(views::reward_list))
        .route("/loyalty/rewards/{reward_id}/", get(views::reward_detail))
        .route(
            "/loyalty/rewards/{reward_id}/redeem/",
            post(views::redeem),
        )
        .route("/loyalty/redemptions/", get(views::redemptions))
        .with_state(state)
}
