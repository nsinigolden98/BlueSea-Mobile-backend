//! Marketplace HTTP layer. Mirrors `market_place/views.py`, split by area:
//! vendor (KYC), events (CRUD, cancel, export), purchase, tickets
//! (list/detail/transfer/cancel), scan (validate, dashboard, scanners),
//! withdrawal (account verify, earnings in/out).

pub mod events;
pub mod purchase;
pub mod scan;
pub mod tickets;
pub mod vendor;
pub mod withdrawal;

use std::collections::HashMap;

use axum::{
    Json,
    extract::{FromRequest, Multipart, Request, State},
    http::{HeaderMap, StatusCode, header::CONTENT_TYPE},
};
use serde_json::{Value, json};

use crate::accounts::models::Profile;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;

pub type Resp = (StatusCode, Json<Value>);

pub fn scheme_host(headers: &HeaderMap) -> (String, String) {
    let host = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("localhost")
        .to_string();
    let scheme = headers
        .get("x-forwarded-proto")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("http")
        .to_string();
    (scheme, host)
}

pub async fn me(s: &AppState, headers: HeaderMap) -> Result<Profile, AppError> {
    auth_user(State(s.clone()), headers).await
}

pub fn bad(msg: &str) -> Resp {
    (StatusCode::BAD_REQUEST, Json(json!({"error": msg, "state": false})))
}

pub fn bad_error(body: Value) -> Resp {
    (StatusCode::BAD_REQUEST, Json(json!({"error": body, "state": false})))
}

pub fn not_found(msg: &str) -> Resp {
    (StatusCode::NOT_FOUND, Json(json!({"error": msg, "state": false})))
}

pub fn forbidden(msg: &str) -> Resp {
    (StatusCode::FORBIDDEN, Json(json!({"error": msg, "state": false})))
}

pub fn pin_locked(retry_after: i64) -> Resp {
    let retry_min = (retry_after / 60) + 1;
    (
        StatusCode::TOO_MANY_REQUESTS,
        Json(json!({"error": format!("Too many attempts. Try again in {retry_min} minutes.")})),
    )
}

pub async fn verify_pin(
    s: &AppState,
    user_id: i64,
    encrypted_pin: &str,
) -> Result<(), Resp> {
    let r = crate::accounts::pin_security::verify_pin_with_lockout(
        &s.db,
        user_id,
        encrypted_pin,
        &s.config.pin_rsa_private_key_b64,
        s.config.pin_max_attempts as i64,
        s.config.pin_lockout_minutes,
    )
    .await
    .map_err(|_| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": "PIN verification failed", "state": false})),
        )
    })?;
    if r.locked {
        return Err(pin_locked(r.retry_after));
    }
    if !r.ok {
        return Err((StatusCode::BAD_REQUEST, Json(json!({"error": "Invalid transaction PIN", "state": false}))));
    }
    Ok(())
}

/// Normalize a UUID path param (dashed or plain) to stored hex; Django's
/// `<uuid:>` converter 404s on garbage, mirrored here as a JSON 404.
pub fn path_hex(raw: &str) -> Result<String, AppError> {
    crate::market_place::models::norm_id(raw)
        .ok_or_else(|| AppError::not_found("Not found"))
}

pub struct ParsedForm {
    pub fields: HashMap<String, String>,
    pub files: Vec<(String, String, Vec<u8>)>,
}

/// Parse JSON or multipart bodies (DRF accepted both on these views).
pub async fn parse_body(req: Request, max_bytes: usize) -> Result<ParsedForm, AppError> {
    let is_multipart = req
        .headers()
        .get(CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .map(|ct| ct.starts_with("multipart/"))
        .unwrap_or(false);
    let mut out = ParsedForm { fields: HashMap::new(), files: Vec::new() };
    if is_multipart {
        let mut multipart = Multipart::from_request(req, &())
            .await
            .map_err(|_| AppError::bad_request("Invalid multipart body"))?;
        while let Ok(Some(field)) = multipart.next_field().await {
            let name = field.name().unwrap_or("").to_string();
            let filename = field.file_name().map(|f| f.to_string());
            let content_type = field.content_type().map(|c| c.to_string());
            match field.bytes().await {
                Ok(bytes) => {
                    if let Some(fname) = filename {
                        out.files.push((name, format!("{fname}\x00{}", content_type.unwrap_or_default()), bytes.to_vec()));
                    } else if let Ok(text) = String::from_utf8(bytes.to_vec()) {
                        out.fields.entry(name).or_insert(text);
                    }
                }
                Err(_) => continue,
            }
        }
        return Ok(out);
    }
    let body = axum::body::to_bytes(req.into_body(), max_bytes).await.unwrap_or_default();
    if !body.is_empty() {
        if let Ok(Value::Object(map)) = serde_json::from_slice::<Value>(&body) {
            for (k, v) in map {
                match v {
                    Value::String(text) => {
                        out.fields.insert(k, text);
                    }
                    Value::Number(n) => {
                        out.fields.insert(k, n.to_string());
                    }
                    Value::Bool(b) => {
                        out.fields.insert(k, b.to_string());
                    }
                    other @ (Value::Array(_) | Value::Object(_)) => {
                        // e.g. `ticket_types` arrives as a JSON string in
                        // form-data; as JSON it is a real array.
                        out.fields.insert(k, serde_json::to_string(&other).unwrap_or_default());
                    }
                    Value::Null => {}
                }
            }
        }
    }
    Ok(out)
}

impl ParsedForm {
    pub fn file(&self, name: &str) -> Option<(&str, &str, &[u8])> {
        self.files.iter().find_map(|(n, fc, b)| {
            if n == name {
                let (fname, ctype) = fc.split_once('\x00').unwrap_or((fc.as_str(), ""));
                Some((fname, ctype, b.as_slice()))
            } else {
                None
            }
        })
    }
}

/// Django `Profile.get_full_name()` (`"{surname}, {other_names}"`) — used
/// for vendor legal names and purchase attendee autofill.
pub fn full_name(user: &Profile) -> String {
    format!("{}, {}", user.surname, user.other_names)
}

pub fn now_ts() -> i64 {
    chrono::Utc::now().timestamp()
}

pub fn is_valid_email_pub(v: &str) -> bool {
    let v = v.trim();
    match v.split_once('@') {
        Some((local, domain)) => !local.is_empty() && domain.contains('.') && !domain.starts_with('.') && !v.contains(' '),
        None => false,
    }
}

/// Parse an event datetime input (`CreateEventSerializer` accepted ISO
/// strings); returns the Lagos-rendered string and the UTC-naive storage
/// string. Django parsed with TZ awareness; naive inputs were assumed UTC.
pub fn parse_event_date(raw: &str) -> Option<(chrono::NaiveDateTime, String)> {
    let raw = raw.trim();
    // RFC3339 / ISO with offset first.
    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(raw) {
        let naive = dt.naive_utc();
        return Some((naive, crate::time::format_naive(&naive)));
    }
    // Django ISO without offset (assume UTC).
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(raw, "%Y-%m-%dT%H:%M:%S%.f") {
        return Some((dt, crate::time::format_naive(&dt)));
    }
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(raw, "%Y-%m-%dT%H:%M:%S") {
        return Some((dt, crate::time::format_naive(&dt)));
    }
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(raw, "%Y-%m-%d %H:%M:%S%.f") {
        return Some((dt, crate::time::format_naive(&dt)));
    }
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(raw, "%Y-%m-%d %H:%M:%S") {
        return Some((dt, crate::time::format_naive(&dt)));
    }
    None
}
