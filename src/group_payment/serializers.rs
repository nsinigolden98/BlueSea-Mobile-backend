//! Response shapes for groups. Mirrors the inline dicts in
//! `group_payment/views.py` (including the duplicated `sub_number` key in
//! list output, which collapses to one).

use serde::Serialize;
use serde_json::{Value, json};
use utoipa::ToSchema;

use crate::transactions::serializers::format_naive_lagos;

use super::models::MemberRow;

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

pub fn normalize_uuid(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }
    // Django raises ValidationError -> 500 for malformed UUIDs.
    uuid::Uuid::parse_str(trimmed).ok().map(|u| u.hyphenated().to_string())
}

pub fn group_uuid_error(raw: &str) -> Value {
    let msg = format!("[\"{raw}\" is not a valid UUID.]");
    json!({ "error": msg })
}

#[derive(Debug, Serialize, ToSchema)]
pub struct GroupListEntry {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub sub_number: String,
    pub service_type: String,
    pub target_amount: i32,
    pub current_amount: i32,
    pub status: String,
    pub plan: String,
    pub plan_type: Option<String>,
    pub my_role: String,
    pub my_payment_status: String,
    pub my_locked_amount: i64,
    pub my_paid_amount: i64,
    pub member_count: i64,
    pub invite_members: String,
    pub paid_members: i64,
    pub pending_members: i64,
    pub join_code: String,
    pub created_at: String,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct GroupMemberPublic {
    pub id: i64,
    pub email: String,
    pub name: String,
    pub role: String,
    pub joined_at: String,
    pub locked_amount: i32,
    pub profile_picture: Option<String>,
}

pub async fn member_public(
    db: &sqlx::PgPool,
    m: &MemberRow,
) -> GroupMemberPublic {
    let prof: Option<(String, String, String, Option<String>)> = sqlx::query_as(
        "SELECT email, surname, other_names, image FROM accounts_profile WHERE id = $1",
    )
    .bind(m.user_id)
    .fetch_optional(db)
    .await
    .unwrap_or(None);
    let (email, surname, other, image) = prof.unwrap_or_else(|| {
        (
            String::new(),
            String::new(),
            String::new(),
            None,
        )
    });
    GroupMemberPublic {
        id: m.id,
        email,
        name: format!("{surname} {other}"),
        role: m.role.clone(),
        joined_at: format_naive_lagos(&m.joined_at),
        locked_amount: m.locked_amount,
        profile_picture: image
            .filter(|p| !p.is_empty())
            .map(|p| format!("/media/{p}")),
    }
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct CreateGroupBody {
    pub transaction_pin: Option<String>,
    pub name: Option<String>,
    pub description: Option<String>,
    pub service_type: Option<String>,
    pub sub_number: Option<String>,
    pub target_amount: Option<serde_json::Value>,
    pub invite_members: Option<String>,
    pub plan: Option<String>,
    pub plan_type: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AddMemberBody {
    pub group_id: Option<String>,
    pub user_email: Option<String>,
    pub role: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct JoinGroupBody {
    pub transaction_pin: Option<String>,
    pub join_code: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct GroupIdBody {
    pub group_id: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct UpdateGroupBody {
    pub sub_number: Option<String>,
}
