//! Notification response shapes. Mirrors
//! `notifications/serializers.py`.

use serde::Serialize;
use utoipa::ToSchema;

use crate::transactions::serializers::format_created_at_lagos;

use super::models::Notification;

#[derive(Debug, Serialize, ToSchema)]
pub struct NotificationPublic {
    pub id: i64,
    pub title: String,
    pub message: String,
    pub notification_type: String,
    pub is_read: bool,
    pub created_at: String,
    pub read_at: Option<String>,
}

impl NotificationPublic {
    pub fn from_row(n: &Notification, created_raw: &str, read_raw: Option<&str>) -> Self {
        Self {
            id: n.id,
            title: n.title.clone(),
            message: n.message.clone(),
            notification_type: n.notification_type.clone(),
            is_read: n.is_read,
            created_at: format_created_at_lagos(created_raw),
            read_at: read_raw.map(format_created_at_lagos),
        }
    }
}
