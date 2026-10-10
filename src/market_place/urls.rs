//! Route table for marketplace. Mirrors `market_place/urls.py`
//! (mounted at `/marketplace/`).

use axum::{
    Router,
    routing::{get, patch, post},
};

use crate::state::AppState;

use super::views;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/marketplace/vendor/create/", post(views::vendor::create_vendor))
        .route("/marketplace/vendor/status/", get(views::vendor::vendor_status))
        .route("/marketplace/vendor/tickets/", get(views::vendor::vendor_tickets))
        .route("/marketplace/events/create/", post(views::events::create_event))
        .route("/marketplace/events/all/", get(views::events::list_events))
        .route("/marketplace/events/{event_id}/", get(views::events::event_detail))
        .route("/marketplace/events/{event_id}/edit/", patch(views::events::update_event))
        .route("/marketplace/events/{event_id}/cancel/", post(views::events::vendor_cancel))
        .route("/marketplace/events/{event_id}/cancel-status/", get(views::events::cancel_status))
        .route("/marketplace/events/public/{event_id}/", get(views::events::event_public_view))
        .route("/marketplace/events/{event_id}/purchase/", post(views::purchase::purchase))
        .route("/marketplace/tickets/my/", get(views::tickets::my_tickets))
        .route("/marketplace/events/{event_id}/attendees/export/", get(views::events::export_attendees))
        .route("/marketplace/tickets/", get(views::tickets::ticket_list))
        .route("/marketplace/tickets/{ticket_id}/", get(views::tickets::ticket_detail))
        .route("/marketplace/mytickets/", get(views::tickets::my_tickets_list))
        .route("/marketplace/tickets/{ticket_id}/transfer/", post(views::tickets::transfer_ticket))
        .route("/marketplace/tickets/{ticket_id}/cancel/", post(views::tickets::cancel_ticket))
        .route("/marketplace/tickets/scan/", post(views::scan::scan_ticket))
        .route("/marketplace/events/{event_id}/scan-stats/", get(views::scan::scan_stats))
        .route("/marketplace/my-scanner-assignments/", get(views::scan::my_assignments))
        .route("/marketplace/events/{event_id}/scanner/", post(views::scan::add_scanner))
        .route("/marketplace/verify-account-name/", post(views::withdrawal::verify_account_name))
        .route("/marketplace/withdraw/", post(views::withdrawal::withdraw).get(views::withdrawal::withdrawal_history))
        .with_state(state)
}
