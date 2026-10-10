//! Request validation and response shapes for affiliates. Mirrors
//! `affiliate/serializers.py` with DRF's exact error shapes.

use regex::Regex;
use serde::Serialize;
use serde_json::Value;
use utoipa::ToSchema;

use crate::transactions::serializers::format_created_at_lagos;
use crate::wallet::models::dec2;

use super::models::AffiliateProfileRow;

fn err(field: &str, message: &str) -> Value {
    serde_json::json!({ field: [message] })
}

fn coerce_str(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

fn opt_url(body: &Value, name: &str) -> Result<Option<String>, Value> {
    match body.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => {
            if s.trim().is_empty() {
                return Ok(None);
            }
            if s.starts_with("http://") || s.starts_with("https://") {
                Ok(Some(s.clone()))
            } else {
                Err(err(name, "Enter a valid URL."))
            }
        }
        Some(_) => Err(err(name, "Enter a valid URL.")),
    }
}

#[derive(Debug)]
pub struct ApplyParams {    pub affiliate_name: String,
    pub facebook: Option<String>,
    pub instagram: Option<String>,
    pub twitter: Option<String>,
    pub tiktok: Option<String>,
    pub agreement: bool,
}

pub fn validate_apply(body: &Value) -> Result<ApplyParams, Value> {
    let name = match body.get("affiliate_name") {
        None | Some(Value::Null) => return Err(err("affiliate_name", "This field is required.")),
        Some(v) => match coerce_str(v) {
            None => return Err(err("affiliate_name", "Not a valid string.")),
            Some(s) if s.trim().is_empty() => {
                return Err(err("affiliate_name", "This field may not be blank."))
            }
            Some(s) => s,
        },
    };
    if name.chars().count() > 13 {
        return Err(err(
            "affiliate_name",
            "Ensure this field has no more than 13 characters.",
        ));
    }
    let re = Regex::new(r"^[A-Za-z0-9]+$").unwrap();
    if !re.is_match(&name) {
        return Err(err(
            "affiliate_name",
            "Affiliate name can only contain letters and numbers.",
        ));
    }
    let agreement = match body.get("agreement") {
        None | Some(Value::Null) => return Err(err("agreement", "This field is required.")),
        Some(Value::Bool(b)) => {
            if !b {
                return Err(err("agreement", "You must accept the affiliate agreement."));
            }
            true
        }
        Some(_) => return Err(err("agreement", "Must be a valid boolean.")),
    };
    Ok(ApplyParams {
        affiliate_name: name,
        facebook: opt_url(body, "facebook")?,
        instagram: opt_url(body, "instagram")?,
        twitter: opt_url(body, "twitter")?,
        tiktok: opt_url(body, "tiktok")?,
        agreement,
    })
}

#[derive(Debug, Serialize, ToSchema)]
pub struct AffiliateStatusPublic {
    pub id: i64,
    pub affiliate_name: String,
    pub status: String,
    pub is_approved: bool,
    pub commission_rate: String,
    pub facebook: Option<String>,
    pub instagram: Option<String>,
    pub twitter: Option<String>,
    pub tiktok: Option<String>,
    pub agreement_accepted: bool,
    pub rejected_reason: Option<String>,
    pub created_at: String,
}

impl AffiliateStatusPublic {
    pub fn from_row(p: &AffiliateProfileRow, created_raw: &str) -> Self {
        Self {
            id: p.id,
            affiliate_name: p.affiliate_name.clone(),
            status: p.status.clone(),
            is_approved: p.status == "approved",
            commission_rate: dec2(&p.commission_rate),
            facebook: p.facebook.clone(),
            instagram: p.instagram.clone(),
            twitter: p.twitter.clone(),
            tiktok: p.tiktok.clone(),
            agreement_accepted: p.agreement_accepted,
            rejected_reason: p.rejected_reason.clone(),
            created_at: format_created_at_lagos(created_raw),
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct AffiliateLinkPublic {
    pub id: i64,
    pub event: String,
    pub event_title: String,
    pub commission_rate: String,
    pub clicks: i32,
    pub is_active: bool,
    pub link: String,
    pub created_at: String,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct AffiliateSalePublic {
    pub id: i64,
    pub affiliate_name: String,
    pub event: String,
    pub event_title: String,
    pub buyer: i64,
    pub buyer_email: String,
    pub ticket_count: i32,
    pub gross_amount: String,
    pub commission_rate: String,
    pub commission_amount: String,
    pub status: String,
    pub created_at: String,
    pub payable_at: Option<String>,
    pub paid_at: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AffiliateApplyBody {
    pub affiliate_name: Option<String>,
    pub facebook: Option<serde_json::Value>,
    pub instagram: Option<serde_json::Value>,
    pub twitter: Option<serde_json::Value>,
    pub tiktok: Option<serde_json::Value>,
    pub agreement: Option<serde_json::Value>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AffiliateLinkCreateBody {
    pub event_id: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AffiliateAttributionBody {
    pub event_id: Option<String>,
    pub affiliate_username: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn apply_validation_mirrors_drf() {
        let ok = validate_apply(
            &serde_json::json!({"affiliate_name": "Promo123", "agreement": true}),
        )
        .unwrap();
        assert_eq!(ok.affiliate_name, "Promo123");
        let e = validate_apply(
            &serde_json::json!({"affiliate_name": "bad-name!", "agreement": true}),
        )
        .unwrap_err();
        assert_eq!(
            e,
            serde_json::json!({"affiliate_name": ["Affiliate name can only contain letters and numbers."]})
        );
        let e = validate_apply(
            &serde_json::json!({"affiliate_name": "Promo123", "agreement": false}),
        )
        .unwrap_err();
        assert_eq!(
            e,
            serde_json::json!({"agreement": ["You must accept the affiliate agreement."]})
        );
        let e = validate_apply(
            &serde_json::json!({"affiliate_name": "Promo123", "agreement": true, "facebook": "nope"}),
        )
        .unwrap_err();
        assert_eq!(e, serde_json::json!({"facebook": ["Enter a valid URL."]}));
    }
}
