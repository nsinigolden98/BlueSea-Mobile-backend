//! Route table for the accounts app.
//! Mirrors `accounts/urls.py` (all paths mounted under `/accounts/`).

use axum::{Router, routing::{get, post}};

use crate::state::AppState;

use super::{kyc, views};

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/accounts/sign-up/", post(views::auth::sign_up))
        .route("/accounts/login/", post(views::auth::login))
        .route(
            "/accounts/verify-email/",
            post(views::auth::verify_email),
        )
        .route("/accounts/resend-otp/", post(views::auth::resend_otp))
        .route(
            "/accounts/auth/google/",
            post(views::social::google_login),
        )
        .route("/accounts/auth/apple/", post(views::social::apple_login))
        .route(
            "/accounts/password/reset/request/",
            post(views::auth::password_reset_request),
        )
        .route(
            "/accounts/password/reset/verify-otp/",
            post(views::auth::password_reset_verify_otp),
        )
        .route(
            "/accounts/password/reset/confirm/",
            post(views::auth::password_reset_confirm),
        )
        .route("/accounts/logout/", post(views::auth::logout))
        .route("/accounts/pin/set/", post(views::pin::pin_set))
        .route("/accounts/pin/verify/", post(views::pin::pin_verify))
        .route("/accounts/pin/reset/", post(views::pin::pin_change))
        .route(
            "/accounts/transaction/pin/request/",
            post(views::pin::pin_reset_request),
        )
        .route(
            "/accounts/transaction/pin/verify-otp/",
            post(views::pin::pin_reset_verify_otp),
        )
        .route(
            "/accounts/transaction/pin/new/",
            post(views::pin::pin_reset_new),
        )
        .route(
            "/accounts/user/lookup/",
            post(views::lookup::user_lookup),
        )
        .route(
            "/accounts/dva/assign/",
            post(views::lookup::dva_assign),
        )
        .route("/accounts/kyc/", get(kyc::status))
        .route("/accounts/kyc/nin/", post(kyc::submit_nin))
        .route("/accounts/kyc/bvn/", post(kyc::submit_bvn))
        .route("/accounts/kyc/address/", post(kyc::submit_address))
        .route("/accounts/kyc/utility-bill/", post(kyc::upload_bill))
        .with_state(state)
}
