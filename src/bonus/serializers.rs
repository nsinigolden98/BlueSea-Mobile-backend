//! Response shapes for the bonus app. Mirrors
//! `bonus/serializers.py` (live serializers).

use serde::Serialize;
use utoipa::ToSchema;

use crate::transactions::serializers::{format_created_at_lagos, format_naive_lagos};

use super::models::{BonusCampaignRow, BonusHistoryRow, ReferralRow};

pub fn type_label_pub(code: &str) -> &str {
    match code {
        "earned" => "Earned",
        "redeemed" => "Redeemed",
        "adjusted" => "Admin Adjustment",
        "expired" => "Expired",
        "reversed" => "Reversed",
        _ => code,
    }
}

pub fn reason_label_pub(reason: Option<&str>) -> Option<String> {
    reason.map(|r| {
        match r {
            "vtu_purchase" => "VTU Purchase",
            "referral" => "Referral Bonus",
            "daily_login" => "Daily Login",
            "campaign" => "Campaign Bonus",
            "admin_award" => "Admin Award",
            "signup_bonus" => "Signup Bonus",
            "milestone" => "Milestone Reward",
            other => other,
        }
        .to_string()
    })
}

pub fn status_label_pub(status: &str) -> &str {
    match status {
        "pending" => "Pending",
        "completed" => "Completed",
        "expired" => "Expired",
        _ => status,
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct BonusHistoryPublic {
    pub id: i64,
    pub transaction_type: String,
    pub transaction_type_display: String,
    pub points: String,
    pub reason: Option<String>,
    pub reason_display: Option<String>,
    pub description: String,
    pub reference: Option<String>,
    pub balance_before: String,
    pub balance_after: String,
    pub created_at: String,
    pub metadata: Option<serde_json::Value>,
}

impl BonusHistoryPublic {
    pub fn from_row(h: &BonusHistoryRow, created_raw: &str) -> Self {
        Self {
            id: h.id,
            transaction_type: h.transaction_type.clone(),
            transaction_type_display: type_label_pub(&h.transaction_type).to_string(),
            points: crate::wallet::models::dec2(&h.points),
            reason: h.reason.clone(),
            reason_display: reason_label_pub(h.reason.as_deref()),
            description: h.description.clone(),
            reference: h.reference.clone(),
            balance_before: crate::wallet::models::dec2(&h.balance_before),
            balance_after: crate::wallet::models::dec2(&h.balance_after),
            created_at: format_created_at_lagos(created_raw),
            metadata: h
                .metadata
                .as_deref()
                .and_then(|m| serde_json::from_str(m).ok()),
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct BonusCampaignPublic {
    pub id: i64,
    pub name: String,
    pub description: String,
    pub campaign_type: String,
    pub multiplier: String,
    pub bonus_amount: String,
    pub is_active: bool,
    pub is_running: bool,
    pub start_date: String,
    pub end_date: String,
}

impl BonusCampaignPublic {
    pub fn from_row(c: &BonusCampaignRow) -> Self {
        let now = crate::time::now_str();
        let running = c.is_active
            && c.start_date.format("%Y-%m-%d %H:%M:%S%.f").to_string() <= now
            && now <= c.end_date.format("%Y-%m-%d %H:%M:%S%.f").to_string();
        Self {
            id: c.id,
            name: c.name.clone(),
            description: c.description.clone(),
            campaign_type: c.campaign_type.clone(),
            multiplier: crate::wallet::models::dec2(&c.multiplier),
            bonus_amount: crate::wallet::models::dec2(&c.bonus_amount),
            is_active: c.is_active,
            is_running: running,
            start_date: format_naive_lagos(&c.start_date),
            end_date: format_naive_lagos(&c.end_date),
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct ReferralPublic {
    pub id: i64,
    pub referrer_email: String,
    pub referred_user_email: String,
    pub referral_code: String,
    pub status: String,
    pub status_display: String,
    pub bonus_awarded: bool,
    pub first_transaction_completed: bool,
    pub created_at: String,
    pub completed_at: Option<String>,
}

impl ReferralPublic {
    pub async fn from_row(
        db: &sqlx::PgPool,
        r: &ReferralRow,
        created_raw: &str,
        completed_raw: Option<&str>,
    ) -> Self {
        let email = |id: i64| async move {
            sqlx::query_as::<_, (String,)>(
                "SELECT email FROM accounts_profile WHERE id = $1",
            )
            .bind(id)
            .fetch_optional(db)
            .await
            .unwrap_or(None)
            .map(|(e,)| e)
            .unwrap_or_default()
        };
        Self {
            id: r.id,
            referrer_email: email(r.referrer_id).await,
            referred_user_email: email(r.referred_user_id).await,
            referral_code: r.referral_code.clone(),
            status: r.status.clone(),
            status_display: status_label_pub(&r.status).to_string(),
            bonus_awarded: r.bonus_awarded,
            first_transaction_completed: r.first_transaction_completed,
            created_at: format_created_at_lagos(created_raw),
            completed_at: completed_raw.map(format_created_at_lagos),
        }
    }
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct ReferralApplyBody {
    pub referral_code: Option<String>,
}
