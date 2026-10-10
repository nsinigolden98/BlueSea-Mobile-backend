//! Route table for support. Mirrors `support/urls.py`
//! (mounted at `/support/`).

use axum::{
    Router,
    routing::{get, post},
};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/support/", get(views::list_tickets).post(views::create_ticket))
        .route(
            "/support/{ticket_id}/",
            get(views::ticket_detail).post(views::add_message),
        )
        .route("/support/admin/tickets/", get(views::admin_list))
        .route(
            "/support/admin/tickets/{ticket_id}/",
            get(views::admin_detail).patch(views::admin_update),
        )
        .route(
            "/support/admin/tickets/{ticket_id}/reply/",
            post(views::admin_reply),
        )
        .with_state(state)
}
