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
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
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
    pub created_at: chrono::NaiveDateTime,
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
    pub start_date: chrono::NaiveDateTime,
    pub end_date: chrono::NaiveDateTime,
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
    pub multiplier: String,
}

#[derive(Debug, Clone, FromRow)]
pub struct ReferralRow {
    pub id: i64,
    pub status: String,
    pub bonus_awarded: bool,
    pub first_transaction_completed: bool,
    pub created_at: chrono::NaiveDateTime,
    pub completed_at: Option<chrono::NaiveDateTime>,
    pub referred_user_id: i64,
    pub referrer_id: i64,
    pub count: i64,
    pub referral_code: String,
}

pub fn dec(raw: &str) -> Decimal {
    raw.parse::<Decimal>().unwrap_or(Decimal::ZERO)
}

pub async fn get_point(
    db: &sqlx::SqlitePool,
    user_id: i64,
) -> Result<Option<BonusPointRow>, sqlx::Error> {
    sqlx::query_as::<_, BonusPointRow>(
        "SELECT id, CAST(lifetime_earned AS TEXT) AS lifetime_earned, CAST(lifetime_redeemed AS TEXT) AS lifetime_redeemed, last_daily_login,
                created_at, updated_at, user_id, CAST(points AS TEXT) AS points
         FROM bonus_bonuspoint WHERE user_id = ?",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn ensure_point(
    db: &sqlx::SqlitePool,
    user_id: i64,
    now: &str,
) -> Result<BonusPointRow, sqlx::Error> {
    if let Some(p) = get_point(db, user_id).await? {
        return Ok(p);
    }
    sqlx::query(
        "INSERT INTO bonus_bonuspoint (lifetime_earned, lifetime_redeemed, last_daily_login, created_at, updated_at, user_id, points)
         VALUES ('0.00', '0.00', NULL, ?, ?, ?, '0.00')",
    )
    .bind(now)
    .bind(now)
    .bind(user_id)
    .execute(db)
    .await?;
    get_point(db, user_id).await?.ok_or(sqlx::Error::RowNotFound)
}

pub async fn set_point_balances(
    db: &sqlx::SqlitePool,
    id: i64,
    points: &str,
    lifetime_earned: &str,
    lifetime_redeemed: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE bonus_bonuspoint SET points = ?, lifetime_earned = ?, lifetime_redeemed = ?, updated_at = ? WHERE id = ?",
    )
    .bind(points)
    .bind(lifetime_earned)
    .bind(lifetime_redeemed)
    .bind(now)
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn set_last_daily_login(
    db: &sqlx::SqlitePool,
    id: i64,
    date: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE bonus_bonuspoint SET last_daily_login = ? WHERE id = ?")
        .bind(date)
        .bind(id)
        .execute(db)
        .await?;
    Ok(())
}

pub async fn insert_history(
    db: &sqlx::SqlitePool,
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
    let res = sqlx::query(
        "INSERT INTO bonus_bonushistory (transaction_type, points, reason, description, reference,
                balance_before, balance_after, created_at, metadata, created_by_id, user_id)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    )
    .bind(transaction_type)
    .bind(points)
    .bind(reason)
    .bind(description)
    .bind(reference)
    .bind(balance_before)
    .bind(balance_after)
    .bind(now)
    .bind(metadata_json)
    .bind(created_by)
    .bind(user_id)
    .execute(db)
    .await?;
    Ok(res.last_insert_rowid())
}

pub async fn active_campaign(
    db: &sqlx::SqlitePool,
    now: &str,
) -> Result<Option<BonusCampaignRow>, sqlx::Error> {
    // BonusCampaign Meta ordering is -start_date: latest starter wins.
    sqlx::query_as::<_, BonusCampaignRow>(
        "SELECT id, name, description, campaign_type, CAST(bonus_amount AS TEXT) AS bonus_amount, is_active,
                start_date, end_date, created_at, updated_at, CAST(multiplier AS TEXT) AS multiplier
         FROM bonus_bonuscampaign
         WHERE is_active = 1 AND start_date <= ? AND end_date >= ?
         ORDER BY start_date DESC LIMIT 1",
    )
    .bind(now)
    .bind(now)
    .fetch_optional(db)
    .await
}

pub async fn running_campaigns(
    db: &sqlx::SqlitePool,
    now: &str,
) -> Result<Vec<BonusCampaignRow>, sqlx::Error> {
    sqlx::query_as::<_, BonusCampaignRow>(
        "SELECT id, name, description, campaign_type, CAST(bonus_amount AS TEXT) AS bonus_amount, is_active,
                start_date, end_date, created_at, updated_at, CAST(multiplier AS TEXT) AS multiplier
         FROM bonus_bonuscampaign
         WHERE is_active = 1 AND start_date <= ? AND end_date >= ?
         ORDER BY start_date DESC",
    )
    .bind(now)
    .bind(now)
    .fetch_all(db)
    .await
}

pub async fn referral_for_referred(
    db: &sqlx::SqlitePool,
    referred_user_id: i64,
) -> Result<Option<ReferralRow>, sqlx::Error> {
    sqlx::query_as::<_, ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE referred_user_id = ?",
    )
    .bind(referred_user_id)
    .fetch_optional(db)
    .await
}

pub async fn pending_referral(
    db: &sqlx::SqlitePool,
    referrer_id: i64,
    referred_user_id: i64,
) -> Result<Option<ReferralRow>, sqlx::Error> {
    sqlx::query_as::<_, ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE referrer_id = ? AND referred_user_id = ? AND status = 'pending'",
    )
    .bind(referrer_id)
    .bind(referred_user_id)
    .fetch_optional(db)
    .await
}

pub async fn insert_referral(
    db: &sqlx::SqlitePool,
    referrer_id: i64,
    referred_user_id: i64,
    referral_code: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query(
        "INSERT INTO bonus_referral (status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code)
         VALUES ('pending', 0, 0, ?, NULL, ?, ?, 0, ?)",
    )
    .bind(now)
    .bind(referred_user_id)
    .bind(referrer_id)
    .bind(referral_code)
    .execute(db)
    .await?;
    Ok(res.last_insert_rowid())
}

pub async fn complete_referral(
    db: &sqlx::SqlitePool,
    id: i64,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE bonus_referral SET status = 'completed', first_transaction_completed = 1,
         bonus_awarded = 1, completed_at = ? WHERE id = ?",
    )
    .bind(now)
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn referrals_made(
    db: &sqlx::SqlitePool,
    referrer_id: i64,
) -> Result<Vec<ReferralRow>, sqlx::Error> {
    sqlx::query_as::<_, ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE referrer_id = ? ORDER BY created_at DESC",
    )
    .bind(referrer_id)
    .fetch_all(db)
    .await
}

pub async fn signup_bonus_exists(
    db: &sqlx::SqlitePool,
    user_id: i64,
    referred_user_id: i64,
) -> Result<bool, sqlx::Error> {
    let prefix = format!("SIGNUP-{referred_user_id}");
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM bonus_bonushistory WHERE user_id = ? AND reason = 'signup_bonus' AND reference LIKE ?",
    )
    .bind(user_id)
    .bind(format!("{prefix}%"))
    .fetch_optional(db)
    .await?;
    Ok(row.is_some())
}
