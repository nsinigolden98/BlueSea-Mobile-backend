//! Request validation and response shapes for payments.
//! Mirrors `payments/serializers.py` plus the inline `request.data` checks in
//! `payments/views.py`. Validation errors use DRF's exact shapes so clients
//! see identical 400 bodies.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use utoipa::ToSchema;

use crate::transactions::serializers::format_created_at_lagos;
use crate::wallet::models::{cents_to_decimal, parse_cents};

// ---------- DRF-compatible primitives ----------

fn err(field: &str, message: &str) -> Value {
    serde_json::json!({ field: [message] })
}

fn is_blank(v: &Value) -> bool {
    matches!(v, Value::String(s) if s.trim().is_empty())
}

/// Coerce a JSON value the way DRF CharField does: strings as-is, numbers
/// stringified, bools/null/objects rejected.
fn coerce_str(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

pub fn req_str(body: &Value, name: &str) -> Result<String, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Err(err(name, "This field is required.")),
        Some(v) => match coerce_str(v) {
            None => Err(err(name, "Not a valid string.")),
            Some(s) if s.trim().is_empty() => Err(err(name, "This field may not be blank.")),
            Some(s) => Ok(s),
        },
    }
}

pub fn req_str_max(body: &Value, name: &str, max: usize) -> Result<String, Value> {
    let s = req_str(body, name)?;
    if s.chars().count() > max {
        return Err(err(
            name,
            &format!("Ensure this field has no more than {max} characters."),
        ));
    }
    Ok(s)
}

pub fn req_choice(body: &Value, name: &str, choices: &[&str]) -> Result<String, Value> {
    let s = req_str(body, name)?;
    if choices.contains(&s.as_str()) {
        Ok(s)
    } else {
        Err(err(name, &format!("\"{s}\" is not a valid choice.")))
    }
}

/// DRF IntegerField: integers and integer strings only (bools, floats,
/// decimals rejected).
pub fn req_int(body: &Value, name: &str) -> Result<i64, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Err(err(name, "This field is required.")),
        Some(Value::Bool(_)) => Err(err(name, "A valid integer is required.")),
        Some(Value::Number(n)) => {
            if let Some(i) = n.as_i64() {
                // JSON floats like 100.0 fail as_i64 only when fractional;
                // serde_json 100.0.as_i64() is None. Mirror DRF rejection.
                Ok(i)
            } else {
                Err(err(name, "A valid integer is required."))
            }
        }
        Some(Value::String(s)) => {
            if s.trim().is_empty() {
                return Err(err(name, "A valid integer is required."));
            }
            s.trim().parse::<i64>().map_err(|_| err(name, "A valid integer is required."))
        }
        Some(_) => Err(err(name, "A valid integer is required.")),
    }
}

/// Naira purchase amount: integer, within 1..=50_000_000.
/// The upper bound keeps `naira * 100` far from i64 overflow and caps
/// single-purchase exposure; Nomba-side limits still apply.
pub fn req_amount_naira(body: &Value, name: &str) -> Result<i64, Value> {
    let v = req_int(body, name)?;
    if v < 1 {
        return Err(err(name, "Ensure this value is greater than or equal to 1."));
    }
    if v > 50_000_000 {
        return Err(err(name, "Ensure this value is less than or equal to 50000000."));
    }
    Ok(v)
}

/// Saturating naira→kobo for validated amounts (no overflow possible).
pub fn naira_to_cents(naira: i64) -> i64 {
    naira.saturating_mul(100)
}

/// DRF DecimalField with min_value, returned as integer cents.
/// `min_display` is the exact bound text (e.g. "500.00").
pub fn req_decimal_min(
    body: &Value,
    name: &str,
    min_cents: i64,
    min_display: &str,
) -> Result<i64, Value> {
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
    // DRF DecimalField rejects exponents/floats-that-aren't-exact? It accepts
    // anything Decimal() parses, quantized to 2dp. Mirror: accept ≤2dp.
    let cents = parse_cents(&s).map_err(|_| err(name, "A valid number is required."))?;
    if cents < min_cents {
        return Err(err(
            name,
            &format!("Ensure this value is greater than or equal to {min_display}."),
        ));
    }
    Ok(cents)
}

// ---------- request bodies (utoipa schemas) ----------

#[derive(Debug, Deserialize, ToSchema)]
pub struct AirtimeBody {
    pub transaction_pin: Option<String>,
    pub network: Option<String>,
    pub phone_number: Option<String>,
    pub amount: Option<Value>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct DataBody {
    pub transaction_pin: Option<String>,
    pub plan: Option<String>,
    #[serde(rename = "billersCode")]
    pub billers_code: Option<String>,
    pub phone_number: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct CableBody {
    pub transaction_pin: Option<String>,
    #[serde(rename = "billersCode")]
    pub billers_code: Option<String>,
    pub dstv_plan: Option<String>,
    pub gotv_plan: Option<String>,
    pub startimes_plan: Option<String>,
    pub showmax_plan: Option<String>,
    pub subscription_type: Option<String>,
    pub phone_number: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct ElectricityBody {
    pub transaction_pin: Option<String>,
    #[serde(rename = "billerCode")]
    pub biller_code: Option<String>,
    pub amount: Option<Value>,
    pub biller_name: Option<String>,
    pub meter_type: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct PhoneOnlyBody {
    pub transaction_pin: Option<String>,
    pub phone_number: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct JambBody {
    pub transaction_pin: Option<String>,
    #[serde(rename = "billerCode")]
    pub biller_code: Option<String>,
    pub exam_type: Option<String>,
    pub phone_number: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct CustomerVerifyBody {
    pub meter_type: Option<String>,
    pub meter_number: Option<String>,
    pub biller: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct GroupPaymentBody {
    pub transaction_pin: Option<String>,
    pub group_id: Option<String>,
    pub payment_type: Option<String>,
    pub total_amount: Option<Value>,
    pub service_details: Option<Value>,
    pub split_type: Option<String>,
    pub custom_splits: Option<Value>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct InternalTransferBody {
    pub transaction_pin: Option<String>,
    pub email: Option<String>,
    pub amount: Option<Value>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct WithdrawalBody {
    pub account_name: Option<String>,
    pub account_number: Option<String>,
    pub bank_code: Option<String>,
    pub bank_name: Option<String>,
    pub amount: Option<Value>,
    pub transaction_pin: Option<String>,
}

// ---------- validated params ----------

#[derive(Debug)]
pub struct AirtimeParams {
    pub amount_naira: i64,
    pub network: String,
    pub phone: String,
}

pub fn validate_airtime(body: &Value) -> Result<AirtimeParams, Value> {
    let amount = req_amount_naira(body, "amount")?;
    let network = req_choice(body, "network", &["mtn", "airtel", "glo", "9mobile"])?;
    let phone = req_str_max(body, "phone_number", 11)?;
    Ok(AirtimeParams { amount_naira: amount, network, phone })
}

#[derive(Debug)]
pub struct DataParams {
    pub plan: String,
    pub billers_code: String,
    pub phone: String,
}

pub fn validate_data(body: &Value, plans: &[crate::payments::plans::Plan]) -> Result<DataParams, Value> {
    let plan_raw = req_str(body, "plan")?;
    if crate::payments::plans::find_plan(plans, &plan_raw).is_none() {
        return Err(err("plan", &format!("\"{plan_raw}\" is not a valid choice.")));
    }
    let billers_code = req_str_max(body, "billersCode", 20)?;
    let phone = req_str_max(body, "phone_number", 11)?;
    Ok(DataParams { plan: plan_raw, billers_code: billers_code, phone })
}

/// Nomba data validation: `plan` is the Nomba product id from `/ws/plans/`
/// (free-form — validated by Nomba, not against the legacy VTpass catalog).
#[derive(Debug)]
pub struct NombaDataParams {
    pub plan: String,
    pub billers_code: String,
    pub phone: String,
}

pub fn validate_data_nomba(body: &Value) -> Result<NombaDataParams, Value> {
    let plan = req_str_max(body, "plan", 100)?;
    let billers_code = req_str_max(body, "billersCode", 20)?;
    let phone = req_str_max(body, "phone_number", 11)?;
    Ok(NombaDataParams { plan, billers_code, phone })
}

#[derive(Debug)]
pub struct CableParams {
    pub billers_code: String,
    pub plan: String,
    pub subscription_type: Option<String>,
    pub phone: String,
}

pub fn validate_cable(
    body: &Value,
    plan_field: &str,
    plans: &[crate::payments::plans::Plan],
    needs_subscription_type: bool,
) -> Result<CableParams, Value> {
    let billers_code = req_str_max(body, "billersCode", 20)?;
    let plan_raw = req_str(body, plan_field)?;
    if crate::payments::plans::find_plan(plans, &plan_raw).is_none() {
        return Err(err(plan_field, &format!("\"{plan_raw}\" is not a valid choice.")));
    }
    let subscription_type = if needs_subscription_type {
        Some(req_choice(body, "subscription_type", &["change", "renew"])?)
    } else {
        None
    };
    let phone = req_str_max(body, "phone_number", 11)?;
    // NOTE: DRF error key for an invalid plan would be the field name;
    // remap to "plan" is NOT done — the field key is preserved.
    Ok(CableParams { billers_code, plan: plan_raw, subscription_type, phone })
}

/// Nomba cable validation: `plan` is the Nomba plan id from `/ws/plans/`
/// (free-form — validated by Nomba). `subscription_type` is optional
/// (legacy VTpass field, ignored by Nomba).
#[derive(Debug)]
pub struct NombaCableParams {
    pub billers_code: String,
    pub plan: String,
    pub phone: String,
}

pub fn validate_cable_nomba(body: &Value, plan_field: &str) -> Result<NombaCableParams, Value> {
    let billers_code = req_str_max(body, "billersCode", 20)?;
    let plan = req_str_max(body, plan_field, 100)?;
    let phone = req_str_max(body, "phone_number", 11)?;
    Ok(NombaCableParams { billers_code, plan, phone })
}

#[derive(Debug)]
pub struct ElectricityParams {
    pub biller_code: String,
    pub amount_naira: i64,
    pub biller_name: String,
    pub meter_type: String,
}

/// Legacy VTpass disco ids (reference only — electricity providers now come from Nomba).
#[allow(dead_code)]
const BILLERS: &[&str] = &[
    "ikeja-electric", "eko-electric", "kano-electric", "portharcourt-electric",
    "jos-electric", "ibadan-electric", "kaduna-electric", "abuja-electric",
    "enugu-electric", "benin-electric", "aba-electric", "yola-electric",
];

pub fn validate_electricity(body: &Value) -> Result<ElectricityParams, Value> {
    let biller_code = req_str_max(body, "billerCode", 20)?;
    let amount = req_amount_naira(body, "amount")?;
    // Nomba provider ids (see GET /payments/electricity/providers/);
    // any non-blank provider is accepted and validated by Nomba.
    let biller_name = req_str_max(body, "biller_name", 60)?;
    let meter_type = req_choice(body, "meter_type", &["prepaid", "postpaid"])?;
    Ok(ElectricityParams { biller_code, amount_naira: amount, biller_name, meter_type })
}

pub fn validate_phone_only(body: &Value) -> Result<String, Value> {
    req_str_max(body, "phone_number", 11)
}

#[derive(Debug)]
pub struct JambParams {
    pub biller_code: String,
    pub exam_type: String,
    pub phone: String,
}

pub fn validate_jamb(body: &Value) -> Result<JambParams, Value> {
    let biller_code = req_str_max(body, "billerCode", 30)?;
    let exam_type = req_choice(body, "exam_type", &["utme-mock", "utme-no-mock"])?;
    let phone = req_str_max(body, "phone_number", 11)?;
    Ok(JambParams { biller_code, exam_type, phone })
}

#[derive(Debug)]
pub struct WithdrawalParams {
    pub account_name: String,
    pub account_number: String,
    pub bank_code: String,
    pub bank_name: String,
    pub amount_cents: i64,
}

pub fn validate_withdrawal(body: &Value) -> Result<WithdrawalParams, Value> {
    let account_name = req_str_max(body, "account_name", 100)?;
    let account_number = req_str_max(body, "account_number", 10)?;
    let bank_code = req_str_max(body, "bank_code", 10)?;
    let bank_name = req_str_max(body, "bank_name", 50)?;
    let amount_cents = req_decimal_min(body, "amount", 50_000, "500.00")?;
    Ok(WithdrawalParams { account_name, account_number, bank_code, bank_name, amount_cents })
}

// ---------- response shapes ----------

#[derive(Debug, Serialize, ToSchema)]
pub struct WithdrawalPublic {
    pub id: i64,
    pub user: i64,
    pub account_name: String,
    pub account_number: String,
    pub bank_code: String,
    pub bank_name: String,
    pub amount: String,
    pub status: String,
    pub payment_reference: Option<String>,
    pub recipient_code: Option<String>,
    pub transfer_code: Option<String>,
    pub created_at: String,
    pub completed_at: Option<String>,
}

impl WithdrawalPublic {
    pub fn from_row(
        w: &crate::payments::models::WithdrawalRow,
        created_raw: &str,
        completed_raw: Option<&str>,
    ) -> Self {
        let cents = parse_cents(&w.amount).unwrap_or(0);
        Self {
            id: w.id,
            user: w.user_id,
            account_name: w.account_name.clone(),
            account_number: w.account_number.clone(),
            bank_code: w.bank_code.clone(),
            bank_name: w.bank_name.clone(),
            amount: cents_to_decimal(cents),
            status: w.status.clone(),
            payment_reference: w.payment_reference.clone(),
            recipient_code: w.recipient_code.clone(),
            transfer_code: w.transfer_code.clone(),
            created_at: format_created_at_lagos(created_raw),
            completed_at: completed_raw.map(format_created_at_lagos),
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct ContributionPublic {
    pub id: i64,
    pub member_name: String,
    pub member_email: String,
    pub amount: String,
    pub status: String,
    pub created_at: String,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct GroupPaymentPublic {
    pub id: i64,
    pub group: String,
    pub group_name: String,
    pub initiated_by: Option<i64>,
    pub initiated_by_name: Option<String>,
    pub payment_type: String,
    pub total_amount: String,
    pub service_details: Value,
    pub status: String,
    pub vtu_reference: Option<String>,
    pub contributions: Vec<ContributionPublic>,
    pub created_at: String,
    pub updated_at: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drf_error_shapes() {
        let b = serde_json::json!({"network": "mtnx", "phone_number": "08012345678", "amount": 100});
        let e = validate_airtime(&b).unwrap_err();
        assert_eq!(e, serde_json::json!({"network": ["\"mtnx\" is not a valid choice."]}));
        let b = serde_json::json!({"network": "mtn", "phone_number": "080123456789", "amount": "abc"});
        let e = validate_airtime(&b).unwrap_err();
        assert_eq!(e, serde_json::json!({"amount": ["A valid integer is required."]}));
        let b = serde_json::json!({"network": "mtn", "phone_number": "080123456789", "amount": 100});
        let e = validate_airtime(&b).unwrap_err();
        assert_eq!(
            e,
            serde_json::json!({"phone_number": ["Ensure this field has no more than 11 characters."]})
        );
        // JSON numbers coerce like DRF
        let b = serde_json::json!({"network": "mtn", "phone_number": "08012345678", "amount": 100});
        assert!(validate_airtime(&b).is_ok());
        // withdrawal minimum
        let b = serde_json::json!({"account_name": "A", "account_number": "1", "bank_code": "1",
            "bank_name": "B", "amount": "499.99"});
        let e = validate_withdrawal(&b).unwrap_err();
        assert_eq!(
            e,
            serde_json::json!({"amount": ["Ensure this value is greater than or equal to 500.00."]})
        );
    }
}

#[cfg(test)]
mod security_tests {
    use super::*;

    #[test]
    fn amount_bounds_reject_zero_overflow() {
        for bad in [0, -5, 50_000_001, i64::MAX] {
            let b = serde_json::json!({"network": "mtn", "phone_number": "08012345678", "amount": bad});
            assert!(validate_airtime(&b).is_err(), "amount {bad}");
        }
        // Upper bound is safe against kobo overflow.
        let b = serde_json::json!({"network": "mtn", "phone_number": "08012345678", "amount": 50_000_000});
        let p = validate_airtime(&b).unwrap();
        assert_eq!(naira_to_cents(p.amount_naira), 5_000_000_000);
    }

    #[test]
    fn oversized_strings_rejected() {
        let big = "x".repeat(200);
        let b = serde_json::json!({"plan": big, "billersCode": "0801", "phone_number": "0801"});
        assert!(validate_data_nomba(&b).is_err());
        let b = serde_json::json!({"provider": big, "customer_id": "1"});
        // betting caps live in the view layer (req_str_max 60/50).
        assert!(req_str_max(&b, "provider", 60).is_err());
        let b = serde_json::json!({"provider": "MSPORT", "customer_id": big});
        assert!(req_str_max(&b, "customer_id", 50).is_err());
    }
}
