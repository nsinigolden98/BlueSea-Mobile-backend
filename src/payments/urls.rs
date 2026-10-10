//! Route table for the payments app. Mirrors `payments/urls.py`.

use axum::{Router, routing::{get, post}};

use crate::state::AppState;

use super::{nomba_withdrawal, views, webhook};

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/payments/airtime/", post(views::airtime::airtime))
        .route("/payments/airtel-data/", post(views::data::airtel_data))
        .route("/payments/mtn-data/", post(views::data::mtn_data))
        .route("/payments/glo-data/", post(views::data::glo_data))
        .route("/payments/9mobile-data/", post(views::data::ninemobile_data))
        .route("/payments/dstv/", post(views::cable::dstv))
        .route("/payments/gotv/", post(views::cable::gotv))
        .route("/payments/startimes/", post(views::cable::startimes))
        .route("/payments/showmax/", post(views::cable::showmax))
        .route("/payments/electricity/", post(views::electricity::electricity))
        .route("/payments/jamb-registration/", post(views::exam::jamb_registration))
        .route("/payments/waec-result/", post(views::exam::waec_result))
        .route(
            "/payments/waec-registration/",
            post(views::exam::waec_registration),
        )
        .route(
            "/payments/group-payment/",
            post(views::group::create_group_payment),
        )
        .route(
            "/payments/group-payment/history/",
            get(views::group::group_history),
        )
        .route(
            "/payments/electricity/customer/",
            post(views::customer::verify_customer),
        )
        .route(
            "/payments/electricity/providers/",
            get(views::betting::electricity_providers),
        )
        .route(
            "/payments/electricity/lookup/",
            post(views::customer::electricity_lookup),
        )
        .route(
            "/payments/cable/lookup/",
            post(views::customer::cable_lookup),
        )
        .route(
            "/payments/cable/customer/",
            post(views::customer::cable_lookup),
        )
        .route(
            "/payments/betting/providers/",
            get(views::betting::betting_providers),
        )
        .route(
            "/payments/betting/lookup/",
            post(views::customer::betting_lookup),
        )
        .route("/payments/betting/fund/", post(views::betting::fund_betting))
        .route(
            "/payments/internal-transfer/",
            post(views::internal::internal_transfer),
        )
        .route("/payments/withdrawal/", post(views::withdrawal::withdrawal))
        .route(
            "/payments/withdrawal/nomba/",
            post(nomba_withdrawal::withdrawal),
        )
        .route(
            "/payments/status/{reference_id}/",
            get(views::status::payment_status),
        )
        .route("/payments/webhook/vtpass", post(webhook::vtpass_webhook))
        .route("/payments/webhook/vtpass/", post(webhook::vtpass_webhook))
        .with_state(state)
}
