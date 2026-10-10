//! Request/response shapes for the transactions app.
//! Mirrors `transactions/serializers.py` (the live serializers;
//! `WalletFundingSerializer` references a nonexistent `payment_method` field
//! and is dead in Django, so it is not ported).

use chrono::Timelike;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

use crate::wallet::models::{cents_to_decimal, format_naira, parse_cents};

/// Format an already-parsed naive datetime the way DRF renders stored
/// datetimes (project timezone Africa/Lagos).
pub fn format_naive_lagos(dt: &crate::time::NaiveUtc) -> String {
    format_created_at_lagos(&dt.format("%Y-%m-%d %H:%M:%S%.f").to_string())
}

/// DRF renders stored naive datetimes in the project timezone
/// (Africa/Lagos, fixed +01:00, no DST).
pub fn format_created_at_lagos(stored: &str) -> String {
    let naive = crate::time::parse_stored_dt(stored).unwrap_or(chrono::NaiveDateTime::MIN);
    let lagos = naive + chrono::Duration::hours(1);
    if lagos.nanosecond() == 0 {
        format!("{}+01:00", lagos.format("%Y-%m-%dT%H:%M:%S"))
    } else {
        format!("{}+01:00", lagos.format("%Y-%m-%dT%H:%M:%S%.f"))
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct WalletTransactionPublic {
    pub id: i64,
    pub transaction_type: String,
    pub amount: String,
    pub formatted_amount: String,
    pub description: Option<String>,
    pub reference: String,
    pub status: String,
    pub created_at: String,
    /// Mirrors DRF: `Profile` has no username column, so this is null.
    pub username: Option<String>,
}

impl WalletTransactionPublic {
    pub fn from_parts(
        id: i64,
        _wallet_id: i64,
        amount_raw: &str,
        transaction_type: &str,
        status: &str,
        description: Option<String>,
        reference: &str,
        created_at_raw: &str,
    ) -> Self {
        let cents = parse_cents(amount_raw).unwrap_or(0);
        Self {
            id,
            transaction_type: transaction_type.to_string(),
            amount: cents_to_decimal(cents),
            formatted_amount: format_naira(cents),
            description,
            reference: reference.to_string(),
            status: status.to_string(),
            created_at: format_created_at_lagos(created_at_raw),
            username: None,
        }
    }
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct InitializeFundingBody {
    pub amount: String,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct DvaRefreshBody {
    pub date: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct AccountNameBody {
    pub account_number: String,
    pub bank_code: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lagos_timestamp_matches_drf() {
        // Stored naive UTC -> +01:00 Africa/Lagos, microseconds kept.
        assert_eq!(
            format_created_at_lagos("2026-09-17 14:03:56.602494"),
            "2026-09-17T15:03:56.602494+01:00"
        );
        assert_eq!(
            format_created_at_lagos("2026-09-17 14:03:56"),
            "2026-09-17T15:03:56+01:00"
        );
    }

    #[test]
    fn transaction_shapes_match_drf() {
        let p = WalletTransactionPublic::from_parts(
            50, 1, "50", "DEBIT", "COMPLETED", Some("AIRTIME".into()), "R",
            "2026-09-17 14:03:56.602494",
        );
        assert_eq!(p.amount, "50.00");
        assert_eq!(p.formatted_amount, "₦50.00");
        assert_eq!(p.username, None);
        assert_eq!(p.created_at, "2026-09-17T15:03:56.602494+01:00");
    }
}
