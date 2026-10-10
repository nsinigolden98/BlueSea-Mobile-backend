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
    pub cors_allow_all: bool,
    pub cors_allowed_origins: Vec<String>,
    pub secure_ssl_redirect: bool,
}

/// Load `.env` literally: no `$VAR` interpolation, matching how Django
/// consumes the same file. (`dotenvy` expands `$...`, which silently
/// rewrote this repo's `SECRET_KEY` — it contains a literal `$gvk` — and
/// broke every HMAC/JWT cross-check with Django.)
/// Parse `.env` text into pairs without touching the environment.
/// Pure function so tests never race on cwd/process env.
fn parse_dotenv_literal(text: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
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
        if key.is_empty() {
            continue;
        }
        let value = value.trim();
        let unquoted = value.strip_prefix('"').and_then(|v| v.strip_suffix('"')).or_else(|| {
            value.strip_prefix('\'').and_then(|v| v.strip_suffix('\''))
        });
        out.push((key.to_string(), unquoted.unwrap_or(value).to_string()));
    }
    out
}

pub(crate) fn load_dotenv_literal() {
    let Ok(text) = std::fs::read_to_string(".env") else {
        return;
    };
    for (key, value) in parse_dotenv_literal(&text) {
        if std::env::var(&key).is_ok() {
            continue;
        }
        std::env::set_var(key, value);
    }
}

/// Required env var: panics at boot naming the missing key instead of
/// running on a silent default. The `.env` file (or real environment in
/// Docker) is the single source of truth — see README "Deploy".
fn req(key: &str) -> String {
    env::var(key).unwrap_or_else(|_| panic!("Missing required env var {key} — set it in .env"))
}

fn req_bool(key: &str) -> bool {
    match req(key).as_str() {
        "True" | "true" | "1" => true,
        "False" | "false" | "0" => false,
        other => panic!("Env var {key} must be True/False/1/0, got {other:?}"),
    }
}

fn req_num<T: std::str::FromStr>(key: &str) -> T {
    let raw = req(key);
    raw.parse()
        .unwrap_or_else(|_| panic!("Env var {key} must be a number, got {raw:?}"))
}

/// Percent-encode a URL user-info segment (passwords like `a@b` would
/// otherwise split the host). Unreserved set per RFC 3986.
fn url_encode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b"-._~".contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

impl Config {
    pub fn from_env() -> Self {
        load_dotenv_literal();
        let debug = req_bool("DEBUG");
        // DATABASE_URL when set outright, else composed from the Django-style
        // parts (same construction as docker-compose) — never a silent default.
        let database_url = env::var("DATABASE_URL")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .unwrap_or_else(|| {
                format!(
                    "postgres://{}:{}@{}:{}/{}",
                    url_encode(&req("DATABASE_USER")),
                    url_encode(&req("DATABASE_PASSWORD")),
                    req("DATABASE_HOST"),
                    req("DATABASE_PORT"),
                    req("DATABASE_NAME"),
                )
            });
        Self {
            debug,
            database_url,
            secret_key: req("SECRET_KEY"),
            pin_rsa_private_key_b64: req("PIN_RSA_PRIVATE_KEY"),
            pin_max_attempts: req_num("PIN_MAX_ATTEMPTS"),
            pin_lockout_minutes: req_num("PIN_LOCKOUT_MINUTES"),
            google_client_id: req("GOOGLE_CLIENT_ID"),
            google_client_secret: req("GOOGLE_CLIENT_SECRET"),
            // Presence required; empty means the integration is unconfigured
            // (Apple login fails at use-time, as before — never silently).
            apple_client_id: req("APPLE_CLIENT_ID"),
            site_url: req("SITE_URL"),
            email_backend: req("EMAIL_BACKEND"),
            brevo_api_key: req("BREVO_API_KEY"),
            from_email: {
                let user = env::var("EMAIL_HOST_USER").unwrap_or_default();
                if !user.trim().is_empty() {
                    user
                } else {
                    req("DEFAULT_FROM_EMAIL")
                }
            },
            vtpass_base_url: req("VTPASS_BASE_URL"),
            vtpass_api_key: req("VTPASS_API_KEY"),
            vtpass_secret_key: req("VTPASS_SECRET_KEY"),
            vtpass_public_key: req("VTPASS_PUBLIC_KEY"),
            nomba_client_id: req("NOMBA_CLIENT_ID"),
            nomba_account_id: req("NOMBA_ACCOUNT_ID"),
            nomba_secret_key: req("NOMBA_SECRET_KEY"),
            nomba_signature_key: req("NOMBA_SIGNATURE_KEY"),
            // Mirrors Django (`sandbox=settings.NOMBA_DEBUG`, itself = DEBUG),
            // overridable per environment (Django parses "True"/"False"
            // strings the same way).
            nomba_sandbox: env::var("NOMBA_SANDBOX")
                .ok()
                .filter(|v| !v.trim().is_empty())
                .map(|v| v == "True" || v == "true" || v == "1")
                .unwrap_or(debug),
            media_root: req("MEDIA_ROOT"),
            // Mirrors Django (`CORS_ALLOW_ALL_ORIGINS = DEBUG`), overridable
            // per environment via CORS_ALLOW_ALL_ORIGINS.
            cors_allow_all: env::var("CORS_ALLOW_ALL_ORIGINS")
                .ok()
                .filter(|v| !v.trim().is_empty())
                .map(|v| v == "True" || v == "true" || v == "1")
                .unwrap_or(debug),
            // Mirrors Django (`CORS_ALLOWED_ORIGINS`, comma-separated).
            cors_allowed_origins: env::var("CORS_ALLOWED_ORIGINS")
                .map(|v| {
                    v.split(',')
                        .map(|s| s.trim().to_string())
                        .filter(|s| !s.is_empty())
                        .collect()
                })
                .unwrap_or_default(),
            // Mirrors Django (`SECURE_SSL_REDIRECT = True`, unconditional).
            // kill-switch for local plain-http dev/smoke tests.
            secure_ssl_redirect: env::var("SECURE_SSL_REDIRECT")
                .ok()
                .filter(|v| !v.trim().is_empty())
                .map(|v| !(v == "False" || v == "false" || v == "0"))
                .unwrap_or(true),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dotenv_loader_keeps_dollar_literal() {
        // Regression: dotenvy expanded `$gvk` inside SECRET_KEY, silently
        // changing every HMAC/JWT secret vs Django. The literal parser must
        // preserve `$` verbatim.
        let pairs = parse_dotenv_literal(
            "# comment\nexport LITERAL_LOADER_TEST_KEY=\"ab$cd${EF}gh\"\nEMPTY=\n",
        );
        assert_eq!(
            pairs,
            vec![
                ("LITERAL_LOADER_TEST_KEY".to_string(), "ab$cd${EF}gh".to_string()),
                ("EMPTY".to_string(), String::new()),
            ]
        );
    }

    #[test]
    fn dotenv_loader_preserves_real_secret_key_shape() {
        // The incident shape: double-quoted key with a literal `$gvk`.
        // dotenvy parses this as `...dp^ofjm...` ($gvk expanded to empty);
        // the literal parser must keep it byte-identical.
        let pairs = parse_dotenv_literal(
            "SECRET_KEY=\"django-insecure-fybc+pa&dp^^xnmmsz5fe-c52-ku4xmtt3=1c$gvk^ofjm_b(2\"\n",
        );
        assert_eq!(pairs.len(), 1);
        let (key, value) = &pairs[0];
        assert_eq!(key, "SECRET_KEY");
        assert!(value.contains("$gvk"), "literal $gvk must survive: {value:?}");
        assert!(value.ends_with("b(2"), "closing quote stripped only: {value:?}");
    }

    #[test]
    fn dotenv_loader_skips_comments_and_blank_keys() {
        let pairs = parse_dotenv_literal("# c\n\n   \n=novalue\nOK=yes\n");
        assert_eq!(pairs, vec![("OK".to_string(), "yes".to_string())]);
    }
}
