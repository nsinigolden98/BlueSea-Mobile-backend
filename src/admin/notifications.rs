//! Admin models for `notifications`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "notifications.Notification",
        label: "Notification",
        table: "notifications_notification",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("title", ColType::Text),
        ("message", ColType::Text),
        ("notification_type", ColType::Text),
        ("is_read", ColType::Bool),
        ("created_at", ColType::DateTime),
        ("read_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ("broadcast_id", ColType::Int),
        ],
        search: &["title"],
        default_order: "-created_at",
    });
}
