//! Loyalty rows. Mirrors `bonus/models.py`:
//! BonusPoint, BonusHistory, BonusCampaign, Referral.

use rust_decimal::Decimal;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct BonusPointRow {
    pub id: i64,
    pub lifetime_earned: String,
    pub lifetime_redeemed: String,
    pub last_daily_login: Option<chrono::NaiveDate>,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub user_id: i64,
    pub points: String,
}

#[derive(Debug, Clone, FromRow)]
pub struct BonusHistoryRow {
    pub id: i64,
    pub transaction_type: String,
    pub points: String,
    pub reason: Option<String>,
    pub description: String,
    pub reference: Option<String>,
    pub balance_before: String,
    pub balance_after: String,
    pub created_at: crate::time::NaiveUtc,
    pub metadata: Option<String>,
    pub created_by_id: Option<i64>,
    pub user_id: i64,
}

#[derive(Debug, Clone, FromRow)]
pub struct BonusCampaignRow {
    pub id: i64,
    pub name: String,
    pub description: String,
    pub campaign_type: String,
    pub bonus_amount: String,
    pub is_active: bool,
    pub start_date: crate::time::NaiveUtc,
    pub end_date: crate::time::NaiveUtc,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub multiplier: String,
}

#[derive(Debug, Clone, FromRow)]
pub struct ReferralRow {
    pub id: i64,
    pub status: String,
    pub bonus_awarded: bool,
    pub first_transaction_completed: bool,
    pub created_at: crate::time::NaiveUtc,
    pub completed_at: Option<crate::time::NaiveUtc>,
    pub referred_user_id: i64,
    pub referrer_id: i64,
    pub count: i32,
    pub referral_code: String,
}

pub fn dec(raw: &str) -> Decimal {
    raw.parse::<Decimal>().unwrap_or(Decimal::ZERO)
}

pub async fn get_point(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<BonusPointRow>, sqlx::Error> {
    sqlx::query_as::<_, BonusPointRow>(
        "SELECT id, CAST(lifetime_earned AS TEXT) AS lifetime_earned, CAST(lifetime_redeemed AS TEXT) AS lifetime_redeemed, last_daily_login,
                created_at, updated_at, user_id, CAST(points AS TEXT) AS points
         FROM bonus_bonuspoint WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn ensure_point(
    db: &sqlx::PgPool,
    user_id: i64,
    now: &str,
) -> Result<BonusPointRow, sqlx::Error> {
    if let Some(p) = get_point(db, user_id).await? {
        return Ok(p);
    }
    sqlx::query(
        "INSERT INTO bonus_bonuspoint (lifetime_earned, lifetime_redeemed, last_daily_login, created_at, updated_at, user_id, points)
         VALUES ('0.00', '0.00', NULL, $1, $2, $3, '0.00')",
    )
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .execute(db)
    .await?;
    get_point(db, user_id).await?.ok_or(sqlx::Error::RowNotFound)
}

pub async fn set_point_balances(
    db: &sqlx::PgPool,
    id: i64,
    points: &str,
    lifetime_earned: &str,
    lifetime_redeemed: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE bonus_bonuspoint SET points = CAST($1 AS NUMERIC), lifetime_earned = CAST($2 AS NUMERIC), lifetime_redeemed = CAST($3 AS NUMERIC), updated_at = $4 WHERE id = $5",
    )
    .bind(points)
    .bind(lifetime_earned)
    .bind(lifetime_redeemed)
    .bind(crate::time::Ts(&now))
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn set_last_daily_login(
    db: &sqlx::PgPool,
    id: i64,
    date: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE bonus_bonuspoint SET last_daily_login = $1 WHERE id = $2")
        .bind(crate::time::Ts(&date))
        .bind(id)
        .execute(db)
        .await?;
    Ok(())
}

pub async fn insert_history(
    db: &sqlx::PgPool,
    user_id: i64,
    transaction_type: &str,
    points: &str,
    reason: Option<&str>,
    description: &str,
    reference: Option<&str>,
    balance_before: &str,
    balance_after: &str,
    created_by: Option<i64>,
    metadata_json: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO bonus_bonushistory (transaction_type, points, reason, description, reference,
                balance_before, balance_after, created_at, metadata, created_by_id, user_id)
         VALUES ($1, CAST($2 AS NUMERIC), $3, $4, $5, CAST($6 AS NUMERIC), CAST($7 AS NUMERIC), $8, CAST($9 AS JSONB), $10, $11) RETURNING id",
    )
    .bind(transaction_type)
    .bind(points)
    .bind(reason)
    .bind(description)
    .bind(reference)
    .bind(balance_before)
    .bind(balance_after)
    .bind(crate::time::Ts(&now))
    .bind(metadata_json)
    .bind(created_by)
    .bind(user_id)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn active_campaign(
    db: &sqlx::PgPool,
    now: &str,
) -> Result<Option<BonusCampaignRow>, sqlx::Error> {
    // BonusCampaign Meta ordering is -start_date: latest starter wins.
    sqlx::query_as::<_, BonusCampaignRow>(
        "SELECT id, name, description, campaign_type, CAST(bonus_amount AS TEXT) AS bonus_amount, is_active,
                start_date, end_date, created_at, updated_at, CAST(multiplier AS TEXT) AS multiplier
         FROM bonus_bonuscampaign
         WHERE is_active = TRUE AND start_date <= $1 AND end_date >= $2
         ORDER BY start_date DESC LIMIT 1",
    )
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .fetch_optional(db)
    .await
}

pub async fn running_campaigns(
    db: &sqlx::PgPool,
    now: &str,
) -> Result<Vec<BonusCampaignRow>, sqlx::Error> {
    sqlx::query_as::<_, BonusCampaignRow>(
        "SELECT id, name, description, campaign_type, CAST(bonus_amount AS TEXT) AS bonus_amount, is_active,
                start_date, end_date, created_at, updated_at, CAST(multiplier AS TEXT) AS multiplier
         FROM bonus_bonuscampaign
         WHERE is_active = TRUE AND start_date <= $1 AND end_date >= $2
         ORDER BY start_date DESC",
    )
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .fetch_all(db)
    .await
}

pub async fn referral_for_referred(
    db: &sqlx::PgPool,
    referred_user_id: i64,
) -> Result<Option<ReferralRow>, sqlx::Error> {
    sqlx::query_as::<_, ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE referred_user_id = $1",
    )
    .bind(referred_user_id)
    .fetch_optional(db)
    .await
}

pub async fn pending_referral(
    db: &sqlx::PgPool,
    referrer_id: i64,
    referred_user_id: i64,
) -> Result<Option<ReferralRow>, sqlx::Error> {
    sqlx::query_as::<_, ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE referrer_id = $1 AND referred_user_id = $2 AND status = 'pending'",
    )
    .bind(referrer_id)
    .bind(referred_user_id)
    .fetch_optional(db)
    .await
}

pub async fn insert_referral(
    db: &sqlx::PgPool,
    referrer_id: i64,
    referred_user_id: i64,
    referral_code: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO bonus_referral (status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code)
         VALUES ('pending', FALSE, FALSE, $1, NULL, $2, $3, 0, $4) RETURNING id",
    )
    .bind(crate::time::Ts(&now))
    .bind(referred_user_id)
    .bind(referrer_id)
    .bind(referral_code)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn complete_referral(
    db: &sqlx::PgPool,
    id: i64,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE bonus_referral SET status = 'completed', first_transaction_completed = TRUE,
         bonus_awarded = TRUE, completed_at = $1 WHERE id = $2",
    )
    .bind(crate::time::Ts(&now))
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn referrals_made(
    db: &sqlx::PgPool,
    referrer_id: i64,
) -> Result<Vec<ReferralRow>, sqlx::Error> {
    sqlx::query_as::<_, ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE referrer_id = $1 ORDER BY created_at DESC",
    )
    .bind(referrer_id)
    .fetch_all(db)
    .await
}

pub async fn signup_bonus_exists(
    db: &sqlx::PgPool,
    user_id: i64,
    referred_user_id: i64,
) -> Result<bool, sqlx::Error> {
    let prefix = format!("SIGNUP-{referred_user_id}");
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM bonus_bonushistory WHERE user_id = $1 AND reason = 'signup_bonus' AND reference LIKE $2",
    )
    .bind(user_id)
    .bind(format!("{prefix}%"))
    .fetch_optional(db)
    .await?;
    Ok(row.is_some())
}
