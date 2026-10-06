//! Route table for the bonus app. Mirrors `bonus/urls.py`.

use axum::{Router, routing::get};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/bonus/summary/", get(views::summary))
        .route("/bonus/history/", get(views::history))
        .route("/bonus/daily-login/", get(views::daily_login))
        .route("/bonus/campaigns/", get(views::campaigns))
        .route(
            "/bonus/referral/",
            get(views::referral_list).post(views::referral_apply),
        )
        .with_state(state)
}
