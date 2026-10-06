//! OpenAPI documentation. Mirrors `drf-spectacular` (`/schema/`, `/docs/`,
//! `/redoc/`): every ported endpoint is annotated with `#[utoipa::path]`
//! next to its handler and registered here.

use utoipa::{
    Modify, OpenApi,
    openapi::security::{HttpAuthScheme, HttpBuilder, SecurityScheme},
};

struct SecurityAddon;

impl Modify for SecurityAddon {
    fn modify(&self, openapi: &mut utoipa::openapi::OpenApi) {
        if let Some(components) = openapi.components.as_mut() {
            components.add_security_scheme(
                "bearer",
                SecurityScheme::Http(
                    HttpBuilder::new()
                        .scheme(HttpAuthScheme::Bearer)
                        .bearer_format("JWT")
                        .build(),
                ),
            );
        }
    }
}

#[derive(OpenApi)]
#[openapi(
    info(title = "BlueSea Mobile API", version = "1.0.0"),
    modifiers(&SecurityAddon),
    tags(
        (name = "Authentication", description = "Signup, login, verification, password reset, PIN and DVA"),
        (name = "Wallet", description = "Balance and real-time updates"),
        (name = "Wallet & Transactions", description = "History, Paystack funding and DVA requery"),
        (name = "Payments", description = "Airtime, data, cable, electricity and exam purchases"),
        (name = "Withdrawal", description = "Bank withdrawals via Paystack"),
        (name = "User Profile", description = "Profile details and preferences"),
        (name = "Notifications", description = "In-app notifications"),
        (name = "Bonus & Rewards", description = "Points, campaigns and referrals"),
    ),
    paths(
        crate::accounts::views::auth::sign_up,
        crate::accounts::views::auth::login,
        crate::accounts::views::auth::verify_email,
        crate::accounts::views::auth::resend_otp,
        crate::accounts::views::auth::logout,
        crate::accounts::views::auth::password_reset_request,
        crate::accounts::views::auth::password_reset_verify_otp,
        crate::accounts::views::auth::password_reset_confirm,
        crate::accounts::views::social::google_login,
        crate::accounts::views::social::apple_login,
        crate::accounts::views::pin::pin_set,
        crate::accounts::views::pin::pin_verify,
        crate::accounts::views::pin::pin_change,
        crate::accounts::views::pin::pin_reset_request,
        crate::accounts::views::pin::pin_reset_verify_otp,
        crate::accounts::views::pin::pin_reset_new,
        crate::accounts::views::lookup::user_lookup,
        crate::accounts::views::lookup::dva_assign,
        crate::wallet::views::balance,
        crate::transactions::views::history::history,
        crate::transactions::views::funding::initialize_funding,
        crate::transactions::views::account_name::account_name,
        crate::transactions::views::dva_refresh::dva_refresh,
        crate::payments::views::airtime::airtime,
        crate::payments::views::data::mtn_data,
        crate::payments::views::data::airtel_data,
        crate::payments::views::data::glo_data,
        crate::payments::views::data::etisalat_data,
        crate::payments::views::cable::dstv,
        crate::payments::views::cable::gotv,
        crate::payments::views::cable::startimes,
        crate::payments::views::cable::showmax,
        crate::payments::views::electricity::electricity,
        crate::payments::views::exam::waec_registration,
        crate::payments::views::exam::waec_result,
        crate::payments::views::exam::jamb_registration,
        crate::payments::views::customer::verify_customer,
        crate::payments::views::group::create_group_payment,
        crate::payments::views::group::group_history,
        crate::payments::views::internal::internal_transfer,
        crate::payments::views::withdrawal::withdrawal,
        crate::payments::views::status::payment_status,
        crate::user_preference::views::current_user,
        crate::user_preference::views::update_user,
        crate::user_preference::views::check_user,
        crate::notifications::views::list,
        crate::notifications::views::mark_read,
        crate::notifications::views::mark_all_read,
        crate::notifications::views::delete,
        crate::bonus::views::summary,
        crate::bonus::views::history,
        crate::bonus::views::daily_login,
        crate::bonus::views::campaigns,
        crate::bonus::views::referral_list,
        crate::bonus::views::referral_apply,
    ),
    components(schemas(
        crate::accounts::serializers::ProfilePublic,
        crate::accounts::serializers::SignUpBody,
        crate::accounts::serializers::OtpBody,
        crate::accounts::serializers::LoginBody,
        crate::accounts::serializers::EmailOnlyBody,
        crate::accounts::serializers::ResetConfirmBody,
        crate::accounts::serializers::LogoutBody,
        crate::accounts::serializers::SetPinBody,
        crate::accounts::serializers::ChangePinBody,
        crate::accounts::serializers::VerifyPinBody,
        crate::accounts::serializers::OtpOnlyBody,
        crate::accounts::serializers::NewPinBody,
        crate::accounts::serializers::LookupBody,
        crate::accounts::serializers::GoogleLoginBody,
        crate::accounts::serializers::AppleLoginBody,
        crate::accounts::serializers::DvaAssignBody,
        crate::wallet::serializers::WalletPublic,
        crate::transactions::serializers::WalletTransactionPublic,
        crate::transactions::serializers::InitializeFundingBody,
        crate::transactions::serializers::DvaRefreshBody,
        crate::transactions::serializers::AccountNameBody,
        crate::payments::serializers::AirtimeBody,
        crate::payments::serializers::DataBody,
        crate::payments::serializers::CableBody,
        crate::payments::serializers::ElectricityBody,
        crate::payments::serializers::PhoneOnlyBody,
        crate::payments::serializers::JambBody,
        crate::payments::serializers::CustomerVerifyBody,
        crate::payments::serializers::GroupPaymentBody,
        crate::payments::serializers::InternalTransferBody,
        crate::payments::serializers::WithdrawalBody,
        crate::payments::serializers::WithdrawalPublic,
        crate::payments::serializers::ContributionPublic,
        crate::payments::serializers::GroupPaymentPublic,
        crate::user_preference::serializers::DvaInfo,
        crate::user_preference::serializers::UpdatePreferenceBody,
        crate::notifications::serializers::NotificationPublic,
        crate::bonus::serializers::BonusHistoryPublic,
        crate::bonus::serializers::BonusCampaignPublic,
        crate::bonus::serializers::ReferralPublic,
        crate::bonus::serializers::ReferralApplyBody,
    )),
)]
pub struct ApiDoc;
