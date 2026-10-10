//! Support response shapes. Mirrors `support/serializers.py`.

use serde::Serialize;
use utoipa::ToSchema;

use crate::transactions::serializers::format_created_at_lagos;

use super::models as m;

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct AttachmentPublic {
    pub id: i64,
    pub image: Option<String>,
    pub uploaded_at: String,
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct MessagePublic {
    pub id: i64,
    pub sender_name: String,
    pub message: String,
    pub is_admin: bool,
    pub created_at: String,
    pub attachments: Vec<AttachmentPublic>,
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct TicketPublic {
    pub id: i64,
    pub subject: String,
    pub description: String,
    pub status: String,
    pub priority: String,
    pub created_at: String,
    pub updated_at: String,
    pub messages: Vec<MessagePublic>,
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct AdminTicketPublic {
    pub id: i64,
    pub subject: String,
    pub description: String,
    pub status: String,
    pub priority: String,
    pub created_at: String,
    pub updated_at: String,
    pub messages: Vec<MessagePublic>,
    pub user_name: String,
    pub user_email: String,
    pub message_count: i64,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct CreateTicketBody {
    pub subject: Option<String>,
    pub description: Option<String>,
    pub priority: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AddMessageBody {
    pub message: Option<String>,
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct AdminUpdateBody {
    pub status: Option<String>,
    pub priority: Option<String>,
}

fn absolute_image(scheme: &str, host: &str, stored: &str) -> String {
    format!("{scheme}://{host}/media/{stored}")
}

pub async fn attachment_public(
    db: &sqlx::PgPool,
    a: &m::SupportAttachment,
    scheme: &str,
    host: &str,
) -> AttachmentPublic {
    let uploaded_at = m::raw_attachment_uploaded(db, a.id)
        .await
        .ok()
        .flatten()
        .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&a.uploaded_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    AttachmentPublic {
        id: a.id,
        image: if a.image.is_empty() {
            None
        } else {
            Some(absolute_image(scheme, host, &a.image))
        },
        uploaded_at,
    }
}

pub async fn message_public(
    db: &sqlx::PgPool,
    msg: &m::SupportMessage,
    scheme: &str,
    host: &str,
) -> MessagePublic {
    let sender_name = m::sender_name(db, msg.sender_id).await.unwrap_or_default();
    let created_at = m::raw_created(db, "support_supportmessage", msg.id)
        .await
        .ok()
        .flatten()
        .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&msg.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    let mut attachments = Vec::new();
    if let Ok(rows) = m::attachments_for(db, msg.id).await {
        for a in &rows {
            attachments.push(attachment_public(db, a, scheme, host).await);
        }
    }
    MessagePublic {
        id: msg.id,
        sender_name,
        message: msg.message.clone(),
        is_admin: msg.is_admin,
        created_at,
        attachments,
    }
}

pub async fn ticket_public(
    db: &sqlx::PgPool,
    t: &m::SupportTicket,
    scheme: &str,
    host: &str,
) -> TicketPublic {
    let times = m::raw_ticket_times(db, t.id).await.ok().flatten();
    let (created_at, updated_at) = match times {
        Some((c, u)) => (format_created_at_lagos(&c), format_created_at_lagos(&u)),
        None => (
            format_created_at_lagos(&t.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()),
            format_created_at_lagos(&t.updated_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()),
        ),
    };
    let mut messages = Vec::new();
    if let Ok(rows) = m::messages_for(db, t.id).await {
        for msg in &rows {
            messages.push(message_public(db, msg, scheme, host).await);
        }
    }
    TicketPublic {
        id: t.id,
        subject: t.subject.clone(),
        description: t.description.clone(),
        status: t.status.clone(),
        priority: t.priority.clone(),
        created_at,
        updated_at,
        messages,
    }
}

pub async fn admin_ticket_public(
    db: &sqlx::PgPool,
    t: &m::SupportTicket,
    scheme: &str,
    host: &str,
) -> AdminTicketPublic {
    let base = ticket_public(db, t, scheme, host).await;
    let (user_name, user_email) = m::owner_identity(db, t.user_id).await.unwrap_or_default();
    let message_count = m::message_count(db, t.id).await.unwrap_or(base.messages.len() as i64);
    AdminTicketPublic {
        id: base.id,
        subject: base.subject,
        description: base.description,
        status: base.status,
        priority: base.priority,
        created_at: base.created_at,
        updated_at: base.updated_at,
        messages: base.messages,
        user_name,
        user_email,
        message_count,
    }
}
