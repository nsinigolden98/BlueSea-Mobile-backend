use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub debug: bool,
    pub database_url: String,    pub secret_key: String,
    pub pin_rsa_private_key_b64: String,
    pub pin_max_attempts: i32,
    pub pin_lockout_minutes: i64,
    pub google_client_id: String,
    pub google_client_secret: String,
    pub apple_client_id: String,
    pub site_url: String,
    pub email_backend: String,
    pub brevo_api_key: String,
    pub from_email: String,
    pub vtpass_base_url: String,
    pub vtpass_api_key: String,
    pub vtpass_secret_key: String,
    pub vtpass_public_key: String,
    pub nomba_client_id: String,
    pub nomba_account_id: String,
    pub nomba_secret_key: String,
    pub nomba_signature_key: String,
    pub nomba_sandbox: bool,
    pub media_root: String,
}

/// Load `.env` literally: no `$VAR` interpolation, matching how Django
/// consumes the same file. (`dotenvy` expands `$...`, which silently
/// rewrote this repo's `SECRET_KEY` — it contains a literal `$gvk` — and
/// broke every HMAC/JWT cross-check with Django.)
fn load_dotenv_literal() {
    let Ok(text) = std::fs::read_to_string(".env") else {
        return;
    };
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let line = line.strip_prefix("export ").unwrap_or(line);
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        if key.is_empty() || std::env::var(key).is_ok() {
            continue;
        }
        let value = value.trim();
        let unquoted = value.strip_prefix('"').and_then(|v| v.strip_suffix('"')).or_else(|| {
            value.strip_prefix('\'').and_then(|v| v.strip_suffix('\''))
        });
        std::env::set_var(key, unquoted.unwrap_or(value));
    }
}

impl Config {
    pub fn from_env() -> Self {
        load_dotenv_literal();
        let debug = env::var("DEBUG").map(|v| v == "True" || v == "true" || v == "1").unwrap_or(true);
        let database_url = env::var("DATABASE_URL").unwrap_or_else(|_| {
            "postgres://postgres:postgres@localhost:5432/bluesea_test".to_string()
        });
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
            nomba_client_id: env::var("NOMBA_CLIENT_ID").unwrap_or_default(),
            nomba_account_id: env::var("NOMBA_ACCOUNT_ID").unwrap_or_default(),
            nomba_secret_key: env::var("NOMBA_SECRET_KEY").unwrap_or_default(),
            nomba_signature_key: env::var("NOMBA_SIGNATURE_KEY").unwrap_or_default(),
            // Mirrors Django (`sandbox=settings.NOMBA_DEBUG`, itself = DEBUG),
            // overridable per environment.
            nomba_sandbox: env::var("NOMBA_SANDBOX")
                .map(|v| v == "True" || v == "true" || v == "1")
                .unwrap_or(debug),
            media_root: env::var("MEDIA_ROOT").unwrap_or_else(|_| "./media".to_string()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dotenv_loader_keeps_dollar_literal() {
        // Regression: dotenvy expanded `$gvk` inside SECRET_KEY, silently
        // changing every HMAC/JWT secret vs Django. The literal loader must
        // preserve it (and must not clobber real env vars).
        std::env::remove_var("LITERAL_LOADER_TEST_KEY");
        let dir = std::env::temp_dir().join(format!("dotenv-lit-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join(".env"), "LITERAL_LOADER_TEST_KEY=\"ab$cd${EF}gh\"\n").unwrap();
        let prev = std::env::current_dir().unwrap();
        std::env::set_current_dir(&dir).unwrap();
        load_dotenv_literal();
        std::env::set_current_dir(prev).unwrap();
        assert_eq!(
            std::env::var("LITERAL_LOADER_TEST_KEY").unwrap(),
            "ab$cd${EF}gh"
        );
        std::env::remove_var("LITERAL_LOADER_TEST_KEY");
        std::fs::remove_dir_all(&dir).ok();
    }
}
