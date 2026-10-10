//! Affiliate rows. Mirrors `affiliate/models.py`.
//! Event/ticket FKs point at market-place tables (ported later),
//! read directly via SQL here.

use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct AffiliateProfileRow {
    pub id: i64,
    pub status: String,
    pub commission_rate: String,
    pub facebook: Option<String>,
    pub instagram: Option<String>,
    pub twitter: Option<String>,
    pub tiktok: Option<String>,
    pub agreement_accepted: bool,
    pub rejected_reason: Option<String>,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub user_id: i64,
    pub affiliate_name: String,
}

const PROFILE_COLS: &str = "id, status, CAST(commission_rate AS TEXT) AS commission_rate, facebook,
        instagram, twitter, tiktok, agreement_accepted, rejected_reason, created_at, updated_at,
        user_id, affiliate_name";

#[derive(Debug, Clone, FromRow)]
pub struct AffiliateLinkRow {
    pub id: i64,
    pub commission_rate: String,
    pub clicks: i32,
    pub is_active: bool,
    pub created_at: crate::time::NaiveUtc,
    pub event_id: String,
    pub affiliate_id: i64,
}

#[derive(Debug, Clone, FromRow)]
pub struct AffiliateSaleRow {
    pub id: i64,
    pub ticket_count: i32,
    pub gross_amount: String,
    pub commission_rate: String,
    pub commission_amount: String,
    pub status: String,
    pub created_at: crate::time::NaiveUtc,
    pub payable_at: Option<crate::time::NaiveUtc>,
    pub paid_at: Option<crate::time::NaiveUtc>,
    pub revoked_at: Option<crate::time::NaiveUtc>,
    pub affiliate_id: i64,
    pub buyer_id: i64,
    pub event_id: String,
    pub issued_ticket_id: Option<String>,
    pub link_id: Option<i64>,
}

/// Minimal event view for affiliate logic (market-place table, raw SQL).
pub struct EventView {
    pub id: String,
    pub event_title: String,
    pub is_free: bool,
    pub is_approved: bool,
    pub event_date_raw: String,
}

pub async fn event_by_id(
    db: &sqlx::PgPool,
    id_hex: &str,
) -> Result<Option<EventView>, sqlx::Error> {
    let row: Option<(String, String, bool, bool, String)> = sqlx::query_as(
        "SELECT CAST(id AS TEXT) AS id, event_title, is_free, is_approved, CAST(event_date AS TEXT)
         FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)",
    )
    .bind(id_hex)
    .fetch_optional(db)
    .await?;
    Ok(row.map(|(id, event_title, is_free, is_approved, event_date_raw)| EventView {
        id,
        event_title,
        is_free,
        is_approved,
        event_date_raw,
    }))
}

pub async fn profile_for_user(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<AffiliateProfileRow>, sqlx::Error> {
    sqlx::query_as::<_, AffiliateProfileRow>(&format!(
        "SELECT {PROFILE_COLS} FROM affiliate_affiliateprofile WHERE user_id = $1"
    ))
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn profile_by_name(
    db: &sqlx::PgPool,
    name: &str,
) -> Result<Option<AffiliateProfileRow>, sqlx::Error> {
    sqlx::query_as::<_, AffiliateProfileRow>(&format!(
        "SELECT {PROFILE_COLS} FROM affiliate_affiliateprofile WHERE affiliate_name = $1"
    ))
    .bind(name)
    .fetch_optional(db)
    .await
}

pub async fn name_taken_by_other(
    db: &sqlx::PgPool,
    name: &str,
    user_id: i64,
) -> Result<bool, sqlx::Error> {
    // iexact match excluding self, like the serializer validator.
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM affiliate_affiliateprofile WHERE lower(affiliate_name) = lower($1) AND user_id != $2",
    )
    .bind(name)
    .bind(user_id)
    .fetch_optional(db)
    .await?;
    Ok(row.is_some())
}
