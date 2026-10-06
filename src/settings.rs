use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub debug: bool,
    pub database_url: String,
    pub secret_key: String,
    pub pin_rsa_private_key_b64: String,
    pub pin_max_attempts: i32,
    pub pin_lockout_minutes: i64,
    pub google_client_id: String,
    pub google_client_secret: String,
    pub apple_client_id: String,
    pub paystack_secret_key: String,
    pub site_url: String,
    pub email_backend: String,
    pub brevo_api_key: String,
    pub from_email: String,
    pub vtpass_base_url: String,
    pub vtpass_api_key: String,
    pub vtpass_secret_key: String,
    pub vtpass_public_key: String,
    pub media_root: String,
}

impl Config {
    pub fn from_env() -> Self {
        dotenvy::dotenv().ok();
        let debug = env::var("DEBUG").map(|v| v == "True" || v == "true" || v == "1").unwrap_or(true);
        let database_url = if debug {
            env::var("SQLITE_URL").unwrap_or_else(|_| "sqlite://debug.sqlite3?mode=rwc".to_string())
        } else {
            env::var("DATABASE_URL").expect("DATABASE_URL must be set in production")
        };
        Self {
            debug,
            database_url,
            secret_key: env::var("SECRET_KEY").unwrap_or_else(|_| "dev-insecure-secret-key-change-me".to_string()),
            pin_rsa_private_key_b64: env::var("PIN_RSA_PRIVATE_KEY").unwrap_or_default(),
            pin_max_attempts: env::var("PIN_MAX_ATTEMPTS").ok().and_then(|v| v.parse().ok()).unwrap_or(5),
            pin_lockout_minutes: env::var("PIN_LOCKOUT_MINUTES").ok().and_then(|v| v.parse().ok()).unwrap_or(30),
            google_client_id: env::var("GOOGLE_CLIENT_ID").unwrap_or_default(),
            google_client_secret: env::var("GOOGLE_CLIENT_SECRET").unwrap_or_default(),
            apple_client_id: env::var("APPLE_CLIENT_ID").unwrap_or_default(),
            paystack_secret_key: env::var("PAYSTACK_SECRET_KEY")
                .or_else(|_| env::var("PAYSTACK_SECRET"))
                .unwrap_or_default(),
            site_url: env::var("SITE_URL").unwrap_or_else(|_| "http://localhost:8000".to_string()),
            email_backend: env::var("EMAIL_BACKEND").unwrap_or_else(|_| {
                if debug {
                    "console".to_string()
                } else {
                    "brevo".to_string()
                }
            }),
            brevo_api_key: env::var("BREVO_API_KEY").unwrap_or_default(),
            from_email: {
                let user = env::var("EMAIL_HOST_USER").unwrap_or_default();
                if !user.trim().is_empty() {
                    user
                } else {
                    env::var("DEFAULT_FROM_EMAIL")
                        .unwrap_or_else(|_| "noreply@bluesea.com".to_string())
                }
            },
            vtpass_base_url: env::var("VTPASS_BASE_URL")
                .unwrap_or_else(|_| "https://sandbox.vtpass.com/api".to_string()),
            vtpass_api_key: env::var("VTPASS_API_KEY").unwrap_or_default(),
            vtpass_secret_key: env::var("VTPASS_SECRET_KEY").unwrap_or_default(),
            vtpass_public_key: env::var("VTPASS_PUBLIC_KEY").unwrap_or_default(),
            media_root: env::var("MEDIA_ROOT").unwrap_or_else(|_| "./media".to_string()),
        }
    }
}
