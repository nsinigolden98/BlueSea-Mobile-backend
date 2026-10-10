//! Validation and response shapes for auto top-ups. Mirrors
//! `autotopup/serializers.py` with DRF's exact error shapes.
//! NOTE: the model-level `MinValueValidator(50.00)` maps to the field
//! minimum, so amounts below 50 fail field validation before the custom
//! "Minimum amount is ₦50" check ever runs — mirrored faithfully.

use rust_decimal::Decimal;
use serde::Serialize;
use serde_json::Value;
use utoipa::ToSchema;

use super::models::AutoTopUpRow;

fn err(field: &str, message: &str) -> Value {
    serde_json::json!({ field: [message] })
}

fn err_str(field: &str, message: &str) -> Value {
    serde_json::json!({ field: message })
}

fn coerce_str(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

fn req_str(body: &Value, name: &str) -> Result<String, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Err(err(name, "This field is required.")),
        Some(v) => match coerce_str(v) {
            None => Err(err(name, "Not a valid string.")),
            Some(s) if s.trim().is_empty() => Err(err(name, "This field may not be blank.")),
            Some(s) => Ok(s),
        },
    }
}

fn opt_str(body: &Value, name: &str, max: usize) -> Result<Option<String>, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => match coerce_str(v) {
            None => Err(err(name, "Not a valid string.")),
            Some(s) => {
                if s.chars().count() > max {
                    return Err(err(
                        name,
                        &format!("Ensure this field has no more than {max} characters."),
                    ));
                }
                Ok(Some(s))
            }
        },
    }
}

fn req_max(body: &Value, name: &str, max: usize) -> Result<String, Value> {
    let s = req_str(body, name)?;
    if s.chars().count() > max {
        return Err(err(
            name,
            &format!("Ensure this field has no more than {max} characters."),
        ));
    }
    Ok(s)
}

fn req_choice(body: &Value, name: &str, choices: &[&str]) -> Result<String, Value> {
    let s = req_str(body, name)?;
    if choices.contains(&s.as_str()) {
        Ok(s)
    } else {
        Err(err(name, &format!("\"{s}\" is not a valid choice.")))
    }
}

fn req_decimal(body: &Value, name: &str) -> Result<Decimal, Value> {
    let s = match body.get(name) {
        None | Some(Value::Null) => return Err(err(name, "This field is required.")),
        Some(Value::Bool(_)) => return Err(err(name, "A valid number is required.")),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::String(s)) => {
            if s.trim().is_empty() {
                return Err(err(name, "A valid number is required."));
            }
            s.trim().to_string()
        }
        Some(_) => return Err(err(name, "A valid number is required.")),
    };
    s.parse::<Decimal>()
        .map_err(|_| err(name, "A valid number is required."))
}

fn req_int(body: &Value, name: &str) -> Result<i64, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Err(err(name, "This field is required.")),
        Some(Value::Bool(_)) => Err(err(name, "A valid integer is required.")),
        Some(Value::Number(n)) => n
            .as_i64()
            .ok_or_else(|| err(name, "A valid integer is required.")),
        Some(Value::String(s)) => s
            .trim()
            .parse::<i64>()
            .map_err(|_| err(name, "A valid integer is required.")),
        Some(_) => Err(err(name, "A valid integer is required.")),
    }
}

fn opt_int(body: &Value, name: &str) -> Result<Option<i64>, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(_) => req_int(body, name).map(Some),
    }
}

fn req_bool(body: &Value, name: &str) -> Result<bool, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Err(err(name, "This field is required.")),
        Some(Value::Bool(b)) => Ok(*b),
        Some(_) => Err(err(name, "Must be a valid boolean.")),
    }
}

fn opt_bool(body: &Value, name: &str) -> Result<Option<bool>, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(_) => req_bool(body, name).map(Some),
    }
}

const DATETIME_HINT: &str = "Datetime has wrong format. Use one of these formats instead: YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z].";

/// Parse a DRF datetime input into UTC-naive storage.
/// Naive inputs are interpreted in Africa/Lagos, like Django.
fn parse_datetime_utc(raw: &str) -> Result<chrono::NaiveDateTime, Value> {
    let text = raw.trim();
    // RFC3339 with offset/Z.
    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(text) {
        return Ok(dt.naive_utc());
    }
    // Common variants DRF accepts.
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%.f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%.f%z",
        "%Y-%m-%d %H:%M:%S%z",
    ] {
        if let Ok(dt) = chrono::DateTime::parse_from_str(text, fmt) {
            return Ok(dt.naive_utc());
        }
    }
    // Naive: assume Lagos wall time.
    for fmt in ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S%.f", "%Y-%m-%d %H:%M:%S"] {
        if let Ok(naive) = chrono::NaiveDateTime::parse_from_str(text, fmt) {
            return Ok(naive - chrono::Duration::hours(1));
        }
    }
    Err(err("start_date", DATETIME_HINT))
}

fn req_datetime(body: &Value, name: &str) -> Result<chrono::NaiveDateTime, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Err(err(name, "This field is required.")),
        Some(Value::String(s)) => parse_datetime_utc(s).map_err(|_| err(name, DATETIME_HINT)),
        Some(_) => Err(err(name, DATETIME_HINT)),
    }
}

#[derive(Debug, Clone, Default)]
pub struct TopUpInput {
    pub service_type: Option<String>,
    pub amount: Option<Decimal>,
    pub phone_number: Option<String>,
    pub network: Option<String>,
    pub plan: Option<String>,
    pub start_date: Option<chrono::NaiveDateTime>,
    pub repeat_days: Option<i64>,
    pub is_active: Option<bool>,
}

/// Full validation (create + PUT): required identity fields present.
pub fn validate_full(body: &Value) -> Result<TopUpInput, Value> {
    let service_type = req_choice(body, "service_type", &["airtime", "data"])?;
    let amount = req_decimal(body, "amount")?;
    if amount < Decimal::from(50) {
        return Err(err(
            "amount",
            "Ensure this value is greater than or equal to 50.00.",
        ));
    }
    let phone_number = req_max(body, "phone_number", 20)?;
    validate_phone(&phone_number)?;
    let network = opt_str(body, "network", 20)?.filter(|s| !s.is_empty());
    let plan = opt_str(body, "plan", 100)?.filter(|s| !s.is_empty());
    let start_date = req_datetime(body, "start_date")?;
    let repeat_days = opt_int(body, "repeat_days")?.unwrap_or(0);
    let is_active = opt_bool(body, "is_active")?.unwrap_or(true);

    let input = TopUpInput {
        service_type: Some(service_type),
        amount: Some(amount),
        phone_number: Some(phone_number),
        network,
        plan,
        start_date: Some(start_date),
        repeat_days: Some(repeat_days),
        is_active: Some(is_active),
    };
    validate_business(&input, true)?;
    Ok(input)
}

/// Partial validation (PATCH): only present fields checked.
pub fn validate_partial(body: &Value) -> Result<TopUpInput, Value> {
    let mut input = TopUpInput::default();
    if body.get("service_type").is_some() {
        input.service_type = Some(req_choice(body, "service_type", &["airtime", "data"])?);
    }
    if body.get("amount").is_some() {
        let amount = req_decimal(body, "amount")?;
        if amount < Decimal::from(50) {
            return Err(err(
                "amount",
                "Ensure this value is greater than or equal to 50.00.",
            ));
        }
        input.amount = Some(amount);
    }
    if body.get("phone_number").is_some() {
        let phone = req_max(body, "phone_number", 20)?;
        validate_phone(&phone)?;
        input.phone_number = Some(phone);
    }
    if body.get("network").is_some() {
        input.network = opt_str(body, "network", 20)?.filter(|s| !s.is_empty());
    }
    if body.get("plan").is_some() {
        input.plan = opt_str(body, "plan", 100)?.filter(|s| !s.is_empty());
    }
    if body.get("start_date").is_some() {
        input.start_date = Some(req_datetime(body, "start_date")?);
    }
    if body.get("repeat_days").is_some() {
        input.repeat_days = Some(req_int(body, "repeat_days")?);
    }
    if body.get("is_active").is_some() {
        input.is_active = Some(req_bool(body, "is_active")?);
    }
    validate_business(&input, false)?;
    Ok(input)
}

fn validate_phone(phone: &str) -> Result<(), Value> {
    if !phone.chars().all(|c| c.is_ascii_digit()) {
        return Err(err("phone_number", "Phone number must contain only digits"));
    }
    if phone.len() < 10 || phone.len() > 11 {
        return Err(err(
            "phone_number",
            "Phone number must be 10 or 11 digits",
        ));
    }
    Ok(())
}

/// Business rules from `validate()`: past start, service fields.
/// `full` selects create/PUT semantics (absent service fields fail);
/// partial PATCH applies the same rules to the payload's own service_type.
fn validate_business(input: &TopUpInput, full: bool) -> Result<(), Value> {
    if let Some(start) = input.start_date {
        if start < chrono::Utc::now().naive_utc() {
            return Err(err_str("start_date", "Start date cannot be in the past"));
        }
    }
    let st = input.service_type.as_deref();
    let network_ok = input
        .network
        .as_deref()
        .map(|s| !s.is_empty())
        .unwrap_or(false);
    let plan_ok = input
        .plan
        .as_deref()
        .map(|s| !s.is_empty())
        .unwrap_or(false);
    // Full mode always carries service_type; partial mode only validates the
    // payload's own service_type (Django validates the payload, not the row).
    // Absent service fields fail in both modes when a type is under check,
    // because `data.get(...)` returns None for missing keys.
    let check = full || st.is_some();
    if check {
        match st {
            Some("airtime") if !network_ok => {
                return Err(err_str("network", "Network is required for airtime top-up"));
            }
            Some("data") if !network_ok => {
                return Err(err_str("network", "Network is required for data top-up"));
            }
            Some("data") if !plan_ok => {
                return Err(err_str("plan", "Plan is required for data top-up"));
            }
            _ => {}
        }
    }
    if let Some(amount) = input.amount {
        if amount < Decimal::from(50) {
            return Err(err_str("amount", "Minimum amount is ₦50"));
        }
    }
    Ok(())
}

// ---------- response shapes ----------

#[derive(Debug, Serialize, ToSchema)]
pub struct AutoTopUpPublic {
    pub id: i64,
    pub service_type: String,
    pub amount: String,
    pub phone_number: String,
    pub network: Option<String>,
    pub plan: Option<String>,
    pub start_date: String,
    pub repeat_days: i64,
    pub is_active: bool,
    pub next_run: String,
    pub is_locked: bool,
    pub locked_amount: String,
    pub last_run: Option<String>,
    pub total_runs: i64,
    pub failed_runs: i64,
    pub created_at: String,
    pub updated_at: String,
    pub available_balance: String,
}

pub fn public_from_row(
    t: &AutoTopUpRow,
    start_raw: &str,
    next_raw: &str,
    last_raw: Option<&str>,
    created_raw: &str,
    updated_raw: &str,
    wallet_balance_raw: &str,
) -> AutoTopUpPublic {
    use crate::transactions::serializers::format_created_at_lagos;
    use crate::wallet::models::dec2;
    AutoTopUpPublic {
        id: t.id,
        service_type: t.service_type.clone(),
        amount: dec2(&t.amount),
        phone_number: t.phone_number.clone(),
        network: t.network.clone(),
        plan: t.plan.clone(),
        start_date: format_created_at_lagos(start_raw),
        repeat_days: t.repeat_days as i64,
        is_active: t.is_active,
        next_run: format_created_at_lagos(next_raw),
        is_locked: t.is_locked,
        locked_amount: dec2(&t.locked_amount),
        last_run: last_raw.map(format_created_at_lagos),
        total_runs: t.total_runs as i64,
        failed_runs: t.failed_runs as i64,
        created_at: format_created_at_lagos(created_raw),
        updated_at: format_created_at_lagos(updated_raw),
        available_balance: wallet_balance_raw.to_string(),
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct AutoTopUpHistoryPublic {
    pub id: i64,
    pub service_type: String,
    pub phone_number: String,
    pub amount: String,
    pub status: String,
    pub vtu_reference: Option<String>,
    pub error_message: Option<String>,
    pub executed_at: String,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AutoTopUpCreateBody {
    pub service_type: Option<String>,
    pub amount: Option<serde_json::Value>,
    pub phone_number: Option<String>,
    pub network: Option<String>,
    pub plan: Option<String>,
    pub start_date: Option<String>,
    pub repeat_days: Option<i64>,
    pub is_active: Option<bool>,
    pub transaction_pin: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn body(json: serde_json::Value) -> Value {
        json
    }

    #[test]
    fn full_validation_mirrors_drf() {
        // missing required
        let e = validate_full(&body(json!({}))).unwrap_err();
        assert!(e.get("service_type").is_some());
        // bad choice
        let e = validate_full(&body(json!({
            "service_type": "cable", "amount": "100", "phone_number": "08012345678",
            "start_date": "2030-01-01T00:00:00Z",
        })))
        .unwrap_err();
        assert_eq!(e, json!({"service_type": ["\"cable\" is not a valid choice."]}));
        // below field minimum (model MinValueValidator wins over custom text)
        let e = validate_full(&body(json!({
            "service_type": "airtime", "amount": "40", "phone_number": "08012345678",
            "network": "mtn", "start_date": "2030-01-01T00:00:00Z",
        })))
        .unwrap_err();
        assert_eq!(
            e,
            json!({"amount": ["Ensure this value is greater than or equal to 50.00."]})
        );
        // airtime without network
        let e = validate_full(&body(json!({
            "service_type": "airtime", "amount": "100", "phone_number": "08012345678",
            "start_date": "2030-01-01T00:00:00Z",
        })))
        .unwrap_err();
        assert_eq!(e, json!({"network": "Network is required for airtime top-up"}));
        // bad phone
        let e = validate_full(&body(json!({
            "service_type": "airtime", "amount": "100", "phone_number": "abc",
            "network": "mtn", "start_date": "2030-01-01T00:00:00Z",
        })))
        .unwrap_err();
        assert_eq!(
            e,
            json!({"phone_number": ["Phone number must contain only digits"]})
        );
        // past start
        let e = validate_full(&body(json!({
            "service_type": "airtime", "amount": "100", "phone_number": "08012345678",
            "network": "mtn", "start_date": "2020-01-01T00:00:00Z",
        })))
        .unwrap_err();
        assert_eq!(e, json!({"start_date": "Start date cannot be in the past"}));
        // valid
        let ok = validate_full(&body(json!({
            "service_type": "data", "amount": "500", "phone_number": "08012345678",
            "network": "mtn", "plan": "mtn-1gb-350", "start_date": "2030-01-01T00:00:00Z",
            "repeat_days": 7,
        })))
        .unwrap();
        assert_eq!(ok.repeat_days, Some(7));
        // partial: service_type without network fails like Django
        let e = validate_partial(&body(json!({"service_type": "airtime"}))).unwrap_err();
        assert_eq!(e, json!({"network": "Network is required for airtime top-up"}));
        // partial: unrelated field passes
        assert!(validate_partial(&body(json!({"nickname": "x"}))).is_ok());
    }
}
