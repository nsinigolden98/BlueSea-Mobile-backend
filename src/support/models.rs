//! Support rows. Mirrors `support/models.py`.

use sqlx::FromRow;

pub const STATUSES: &[&str] = &["open", "in_progress", "resolved", "closed"];
pub const PRIORITIES: &[&str] = &["low", "medium", "high", "urgent"];

#[derive(Debug, Clone, FromRow)]
pub struct SupportTicket {
    pub id: i64,
    pub subject: String,
    pub description: String,
    pub status: String,
    pub priority: String,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub user_id: i64,
}

#[derive(Debug, Clone, FromRow)]
pub struct SupportMessage {
    pub id: i64,
    pub message: String,
    pub is_admin: bool,
    pub created_at: crate::time::NaiveUtc,
    pub sender_id: i64,
    pub ticket_id: i64,
}

#[derive(Debug, Clone, FromRow)]
pub struct SupportAttachment {
    pub id: i64,
    pub image: String,
    pub uploaded_at: crate::time::NaiveUtc,
    pub message_id: i64,
}

pub async fn ticket_owned(
    db: &sqlx::PgPool,
    ticket_id: i64,
    user_id: i64,
) -> Result<Option<SupportTicket>, sqlx::Error> {
    sqlx::query_as::<_, SupportTicket>(
        "SELECT * FROM support_supportticket WHERE id = $1 AND user_id = $2",
    )
    .bind(ticket_id)
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn ticket_any(
    db: &sqlx::PgPool,
    ticket_id: i64,
) -> Result<Option<SupportTicket>, sqlx::Error> {
    sqlx::query_as::<_, SupportTicket>("SELECT * FROM support_supportticket WHERE id = $1")
        .bind(ticket_id)
        .fetch_optional(db)
        .await
}

pub async fn messages_for(
    db: &sqlx::PgPool,
    ticket_id: i64,
) -> Result<Vec<SupportMessage>, sqlx::Error> {
    sqlx::query_as::<_, SupportMessage>(
        "SELECT * FROM support_supportmessage WHERE ticket_id = $1 ORDER BY id ASC",
    )
    .bind(ticket_id)
    .fetch_all(db)
    .await
}

pub async fn attachments_for(
    db: &sqlx::PgPool,
    message_id: i64,
) -> Result<Vec<SupportAttachment>, sqlx::Error> {
    sqlx::query_as::<_, SupportAttachment>(
        "SELECT * FROM support_supportattachment WHERE message_id = $1 ORDER BY id ASC",
    )
    .bind(message_id)
    .fetch_all(db)
    .await
}

pub async fn message_count(
    db: &sqlx::PgPool,
    ticket_id: i64,
) -> Result<i64, sqlx::Error> {
    let row: (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM support_supportmessage WHERE ticket_id = $1")
            .bind(ticket_id)
            .fetch_one(db)
            .await?;
    Ok(row.0)
}

pub async fn sender_name(
    db: &sqlx::PgPool,
    sender_id: i64,
) -> Result<String, sqlx::Error> {
    let row: Option<(String, String)> =
        sqlx::query_as("SELECT surname, other_names FROM accounts_profile WHERE id = $1")
            .bind(sender_id)
            .fetch_optional(db)
            .await?;
    Ok(row
        .map(|(s, o)| format!("{s} {o}").trim().to_string())
        .unwrap_or_default())
}

pub async fn owner_identity(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<(String, String), sqlx::Error> {
    let row: Option<(String, String, String)> = sqlx::query_as(
        "SELECT surname, other_names, email FROM accounts_profile WHERE id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await?;
    Ok(row.map(|(s, o, e)| (format!("{s} {o}").trim().to_string(), e)).unwrap_or_default())
}

pub async fn raw_created(
    db: &sqlx::PgPool,
    table: &str,
    id: i64,
) -> Result<Option<String>, sqlx::Error> {
    let sql = format!("SELECT CAST(created_at AS TEXT) FROM {table} WHERE id = $1");
    let row: Option<(String,)> = sqlx::query_as(&sql).bind(id).fetch_optional(db).await?;
    Ok(row.map(|r| r.0))
}

pub async fn raw_ticket_times(
    db: &sqlx::PgPool,
    id: i64,
) -> Result<Option<(String, String)>, sqlx::Error> {
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(created_at AS TEXT), CAST(updated_at AS TEXT) FROM support_supportticket WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(db)
    .await?;
    Ok(row)
}

pub async fn raw_attachment_uploaded(
    db: &sqlx::PgPool,
    id: i64,
) -> Result<Option<String>, sqlx::Error> {
    raw_created(db, "support_supportattachment", id).await
}

pub async fn touch_ticket(
    db: &sqlx::PgPool,
    ticket_id: i64,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE support_supportticket SET updated_at = $1 WHERE id = $2")
        .bind(crate::time::Ts(&now))
        .bind(ticket_id)
        .execute(db)
        .await?;
    Ok(())
}
