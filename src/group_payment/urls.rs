//! Route table for group payments. Mirrors `group_payment/urls.py`
//! (mounted at `/payments/group/`).

use axum::{Router, routing::{get, patch, post}};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/payments/group/create/", post(views::create))
        .route("/payments/group/add-member/", post(views::add_member))
        .route("/payments/group/join-group/", post(views::join))
        .route("/payments/group/my-groups/", get(views::my_groups))
        .route("/payments/group/{group_id}/", get(views::details))
        .route(
            "/payments/group/{group_id}/update/",
            patch(views::update),
        )
        .route("/payments/group/leave/", post(views::leave))
        .route("/payments/group/cancel/", post(views::cancel))
        .with_state(state)
}
