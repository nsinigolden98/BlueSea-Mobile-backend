//! Notification rows. Mirrors `notifications/models.py::Notification`.

use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct Notification {
    pub id: i64,
    pub title: String,
    pub message: String,
    pub notification_type: String,
    pub is_read: bool,
    pub created_at: crate::time::NaiveUtc,
    pub read_at: Option<crate::time::NaiveUtc>,
    pub user_id: i64,
    pub broadcast_id: Option<i64>,
}
