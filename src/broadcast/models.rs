//! Broadcast rows. Mirrors `broadcast/models.py`.

use sqlx::FromRow;

pub const KINDS: &[&str] = &["new_month", "important", "announcement"];
pub const TERMINAL_STATUSES: &[&str] = &["sending", "sent", "partial"];

#[derive(Debug, Clone, FromRow)]
pub struct Broadcast {
    pub id: i64,
    pub kind: String,
    pub title: String,
    pub message: String,
    pub email_subject: String,
    pub template: String,
    pub month_key: Option<String>,
    pub status: String,
    pub total: i32,
    pub sent_count: i32,
    pub failed_count: i32,
    pub created_by_id: Option<i64>,
    pub created_at: crate::time::NaiveUtc,
    pub completed_at: Option<crate::time::NaiveUtc>,
}

pub async fn already_sent(
    db: &sqlx::PgPool,
    kind: &str,
    month_key: Option<&str>,
) -> Result<bool, sqlx::Error> {
    let row: (i64,) = if let Some(mk) = month_key {
        sqlx::query_as(
            "SELECT COUNT(*) FROM broadcast_broadcast
             WHERE kind = $1 AND month_key = $2 AND status IN ('sending', 'sent', 'partial')",
        )
        .bind(kind)
        .bind(mk)
        .fetch_one(db)
        .await?
    } else {
        sqlx::query_as(
            "SELECT COUNT(*) FROM broadcast_broadcast
             WHERE kind = $1 AND status IN ('sending', 'sent', 'partial')",
        )
        .bind(kind)
        .fetch_one(db)
        .await?
    };
    Ok(row.0 > 0)
}

pub async fn recipient_count(db: &sqlx::PgPool) -> Result<i32, sqlx::Error> {
    let row: (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM accounts_profile WHERE is_active = TRUE")
            .fetch_one(db)
            .await?;
    Ok(row.0.try_into().unwrap_or(i32::MAX))
}

pub async fn raw_times(
    db: &sqlx::PgPool,
    id: i64,
) -> Result<Option<(String, Option<String>)>, sqlx::Error> {
    sqlx::query_as(
        "SELECT CAST(created_at AS TEXT), CAST(completed_at AS TEXT) FROM broadcast_broadcast WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(db)
    .await
}
