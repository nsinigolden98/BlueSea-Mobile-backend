//! Loyalty rows. Mirrors `loyalty_market/models.py`:
//! UUID PKs are stored dashless (char(32)); the redemption FK columns are
//! literally `user_id_id` / `reward_id_id` (Django appends `_id` to the
//! `user_id`/`reward_id` field names).

use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct RewardRow {
    pub id: String,
    pub title: String,
    pub description: String,
    pub image_url: Option<String>,
    pub points_cost: i64,
    pub category: Option<String>,
    pub inventory: Option<i64>,
    pub availability_end: Option<chrono::NaiveDateTime>,
    pub fulfilment_type: String,
    pub polarity_score: i64,
    pub created_at: chrono::NaiveDateTime,
    pub user_id: i64,
    pub availability_start: chrono::NaiveDateTime,
}

const REWARD_COLS: &str = "id, title, description, image_url, points_cost, category, inventory,
        availability_end, fulfilment_type, polarity_score, created_at, user_id, availability_start";

pub async fn available_rewards(db: &sqlx::SqlitePool) -> Result<Vec<RewardRow>, sqlx::Error> {
    // inventory__gt=0 excludes NULLs and zeros, like Django.
    sqlx::query_as::<_, RewardRow>(&format!(
        "SELECT {REWARD_COLS} FROM loyalty_market_reward WHERE inventory > 0 ORDER BY created_at DESC"
    ))
    .fetch_all(db)
    .await
}

pub async fn reward_by_id(
    db: &sqlx::SqlitePool,
    id_hex: &str,
) -> Result<Option<RewardRow>, sqlx::Error> {
    sqlx::query_as::<_, RewardRow>(&format!(
        "SELECT {REWARD_COLS} FROM loyalty_market_reward WHERE id = ?"
    ))
    .bind(id_hex)
    .fetch_optional(db)
    .await
}

#[derive(Debug, Clone, FromRow)]
pub struct RedemptionRow {
    pub id: String,
    pub points_deducted: i64,
    pub status: String,
    pub created_at: chrono::NaiveDateTime,
    pub redeemed_at: Option<chrono::NaiveDateTime>,
    pub fulfilment_payload: Option<String>,
    pub user_id_id: i64,
    pub reward_id_id: String,
}

pub async fn redemptions_for(
    db: &sqlx::SqlitePool,
    user_id: i64,
) -> Result<Vec<(RedemptionRow, Option<String>)>, sqlx::Error> {
    // (redemption, reward title or "Unknown"), newest first.
    let rows: Vec<(
        String, i64, String, chrono::NaiveDateTime, Option<chrono::NaiveDateTime>,
        Option<String>, i64, String, Option<String>,
    )> = sqlx::query_as(
        "SELECT r.id, r.points_deducted, r.status, r.created_at, r.redeemed_at,
                r.fulfilment_payload, r.user_id_id, r.reward_id_id, w.title
         FROM loyalty_market_redemptiontransaction r
         LEFT JOIN loyalty_market_reward w ON w.id = r.reward_id_id
         WHERE r.user_id_id = ? ORDER BY r.created_at DESC",
    )
    .bind(user_id)
    .fetch_all(db)
    .await?;
    Ok(rows
        .into_iter()
        .map(
            |(id, points, status, created, redeemed, payload, uid, rid, title)| {
                (
                    RedemptionRow {
                        id,
                        points_deducted: points,
                        status,
                        created_at: created,
                        redeemed_at: redeemed,
                        fulfilment_payload: payload,
                        user_id_id: uid,
                        reward_id_id: rid,
                    },
                    title,
                )
            },
        )
        .collect())
}
