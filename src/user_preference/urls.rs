//! Route table for user preferences. Mirrors
//! `user_preference/urls.py` (`user/`, `check/<email>/`).

use axum::{Router, routing::get};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/user_preference/user/", get(views::current_user).patch(views::update_user))
        .route("/user_preference/check/{email}/", get(views::check_user))
        .with_state(state)
}
