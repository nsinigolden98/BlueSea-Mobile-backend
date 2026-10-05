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
    )),
)]
pub struct ApiDoc;
