//! Response shapes for the loyalty market. Mirrors
//! `loyalty_market/serializers.py` (`RewardSerializer` with all fields,
//! redemption entries with datetimes in project time).

use serde::Serialize;
use utoipa::ToSchema;

use crate::transactions::serializers::format_created_at_lagos;

use super::models::RewardRow;

#[derive(Debug, Serialize, ToSchema)]
pub struct RewardPublic {
    pub id: String,
    pub user: i64,
    pub title: String,
    pub description: String,
    pub image_url: Option<String>,
    pub points_cost: i32,
    pub category: Option<String>,
    pub inventory: Option<i32>,
    pub availability_start: String,
    pub availability_end: Option<String>,
    pub fulfilment_type: String,
    pub polarity_score: i64,
    pub created_at: String,
}

impl RewardPublic {
    pub fn from_row(
        r: &RewardRow,
        start_raw: &str,
        end_raw: Option<&str>,
        created_raw: &str,
    ) -> Self {
        Self {
            // Stored dashless; DRF renders UUID objects with dashes.
            id: dashed_uuid(&r.id),
            user: r.user_id,
            title: r.title.clone(),
            description: r.description.clone(),
            image_url: r.image_url.clone(),
            points_cost: r.points_cost,
            category: r.category.clone(),
            inventory: r.inventory,
            availability_start: format_created_at_lagos(start_raw),
            availability_end: end_raw.map(format_created_at_lagos),
            fulfilment_type: r.fulfilment_type.clone(),
            polarity_score: r.polarity_score,
            created_at: format_created_at_lagos(created_raw),
        }
    }
}

/// Render a dashless 32-hex id the way DRF renders UUIDs.
pub fn dashed_uuid(hex: &str) -> String {
    if hex.len() == 32 {
        format!(
            "{}-{}-{}-{}-{}",
            &hex[0..8], &hex[8..12], &hex[12..16], &hex[16..20], &hex[20..32]
        )
    } else {
        hex.to_string()
    }
}

/// Accept dashed or dashless ids from the path, like Django's UUID converter.
pub fn normalize_uuid(raw: &str) -> String {
    uuid::Uuid::parse_str(raw.trim())
        .map(|u| u.hyphenated().to_string())
        .unwrap_or_default()
}

#[derive(Debug, Serialize, ToSchema)]
pub struct RedemptionPublic {
    pub id: String,
    pub reward: String,
    pub points_deducted: i32,
    pub status: String,
    pub created_at: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uuid_shapes_match_drf() {
        assert_eq!(
            dashed_uuid("12345678123456781234567812345678"),
            "12345678-1234-5678-1234-567812345678"
        );
        assert_eq!(normalize_uuid("12345678123456781234567812345678"), "12345678-1234-5678-1234-567812345678");
    }

    #[test]
    fn lagos_helper_reexport() {
        let _ =
            crate::transactions::serializers::format_naive_lagos(&crate::time::NaiveUtc(chrono::NaiveDateTime::MIN));
    }
}
