//! Broadcast response shapes. Mirrors `broadcast/serializers.py`.

use serde::Serialize;
use utoipa::ToSchema;

use crate::transactions::serializers::format_created_at_lagos;

use super::models as m;

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct BroadcastPublic {
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
    pub created_by: Option<i64>,
    pub created_at: String,
    pub completed_at: Option<String>,
}

pub async fn broadcast_public(db: &sqlx::PgPool, b: &m::Broadcast) -> BroadcastPublic {
    let fallback_created = b.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string();
    let fallback_completed = b.completed_at.map(|dt| dt.format("%Y-%m-%d %H:%M:%S%.f").to_string());
    let (created_at, completed_at) = match m::raw_times(db, b.id).await.ok().flatten() {
        Some((c, comp)) => (
            format_created_at_lagos(&c),
            comp.map(|r| format_created_at_lagos(&r)),
        ),
        None => (
            format_created_at_lagos(&fallback_created),
            fallback_completed.map(|r| format_created_at_lagos(&r)),
        ),
    };
    BroadcastPublic {
        id: b.id,
        kind: b.kind.clone(),
        title: b.title.clone(),
        message: b.message.clone(),
        email_subject: b.email_subject.clone(),
        template: b.template.clone(),
        month_key: b.month_key.clone(),
        status: b.status.clone(),
        total: b.total,
        sent_count: b.sent_count,
        failed_count: b.failed_count,
        created_by: b.created_by_id,
        created_at,
        completed_at,
    }
}
