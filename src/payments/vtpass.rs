//! VTpass API client. Mirrors `payments/vtpass.py`:
//! `top_up` (POST /pay), `get_customer` (POST /merchant-verify),
//! `get_receipt` (POST /requery), `generate_reference_id`
//! (`YYYYMMDDHHMMSS-UUID8`, Lagos wall-clock like Django's `datetime.now()`),
//! and the `api-key`/`public-key`/`secret-key` header set.

use serde_json::Value;

use crate::settings::Config;

fn headers(config: &Config) -> Vec<(String, String)> {
    vec![
        ("api-key".into(), config.vtpass_api_key.trim().to_string()),
        ("public-key".into(), config.vtpass_public_key.trim().to_string()),
        ("secret-key".into(), config.vtpass_secret_key.trim().to_string()),
    ]
}

fn post_json(
    http: &reqwest::Client,
    config: &Config,
    path: &str,
    payload: &Value,
) -> reqwest::RequestBuilder {
    let mut req = http
        .post(format!("{base}{path}", base = config.vtpass_base_url.trim()))
        .json(payload);
    for (k, v) in headers(config) {
        req = req.header(k, v);
    }
    req
}

/// Lagos wall-clock reference id: `YYYYMMDDHHMMSS-XXXXXXXX`
/// (UUID4 first segment, uppercase).
pub fn generate_reference_id() -> String {
    let lagos = chrono::Utc::now() + chrono::Duration::hours(1);
    let stamp = lagos.format("%Y%m%d%H%M%S").to_string();
    let unique = uuid::Uuid::new_v4()
        .simple()
        .to_string()[..8]
        .to_uppercase();
    format!("{stamp}-{unique}")
}

/// POST /pay. Returns the decoded JSON on transport success.
pub async fn top_up(
    http: &reqwest::Client,
    config: &Config,
    payload: &Value,
) -> Result<Value, String> {
    let resp = post_json(http, config, "/pay", payload)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map_err(|e| format!("VTpass request failed: {e}"))?;
    resp.json::<Value>()
        .await
        .map_err(|e| format!("VTpass bad response: {e}"))
}

/// POST /merchant-verify. Returns the decoded JSON on transport success.
pub async fn merchant_verify(
    http: &reqwest::Client,
    config: &Config,
    payload: &Value,
) -> Result<Value, String> {
    let resp = post_json(http, config, "/merchant-verify", payload)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map_err(|e| format!("VTpass request failed: {e}"))?;
    resp.json::<Value>()
        .await
        .map_err(|e| format!("VTpass bad response: {e}"))
}

/// POST /requery with `{"request_id": ...}`. Mirrors `get_receipt`.
pub async fn requery(
    http: &reqwest::Client,
    config: &Config,
    request_id: &str,
) -> Result<Value, String> {
    let payload = serde_json::json!({"request_id": request_id});
    let resp = post_json(http, config, "/requery", &payload)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map_err(|e| format!("VTpass request failed: {e}"))?;
    resp.json::<Value>()
        .await
        .map_err(|e| format!("VTpass bad response: {e}"))
}

pub fn is_successful(resp: &Value) -> bool {
    resp.get("response_description").and_then(|v| v.as_str()) == Some("TRANSACTION SUCCESSFUL")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_shape_matches_django() {
        let r = generate_reference_id();
        assert_eq!(r.len(), 14 + 1 + 8);
        assert_eq!(&r[14..15], "-");
        assert!(r[15..].chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_lowercase()));
        assert!(r[..14].chars().all(|c| c.is_ascii_digit()));
    }

    #[test]
    fn success_detection() {
        assert!(is_successful(&serde_json::json!({"response_description": "TRANSACTION SUCCESSFUL"})));
        assert!(!is_successful(&serde_json::json!({"response_description": "FAILED"})));
    }
}
