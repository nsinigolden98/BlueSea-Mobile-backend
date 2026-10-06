//! Route table for auto top-ups. Mirrors `autotopup/urls.py`.

use axum::{Router, routing::{get, patch, post}};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/autotopup/create/", post(views::create))
        .route("/autotopup/list/", get(views::list))
        .route(
            "/autotopup/{pk}/",
            get(views::detail)
                .put(views::update_full)
                .patch(views::update_partial)
                .delete(views::delete),
        )
        .route("/autotopup/{pk}/cancel/", patch(views::cancel))
        .route("/autotopup/{pk}/reactivate/", patch(views::reactivate))
        .route("/autotopup/{pk}/history/", get(views::history))
        .with_state(state)
}
