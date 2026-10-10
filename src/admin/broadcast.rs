//! Admin models for `broadcast`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "broadcast.Broadcast",
        label: "Broadcast",
        table: "broadcast_broadcast",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("kind", ColType::Text),
        ("title", ColType::Text),
        ("message", ColType::Text),
        ("email_subject", ColType::Text),
        ("template", ColType::Text),
        ("month_key", ColType::Text),
        ("status", ColType::Text),
        ("total", ColType::Int),
        ("sent_count", ColType::Int),
        ("failed_count", ColType::Int),
        ("created_at", ColType::DateTime),
        ("completed_at", ColType::DateTime),
        ("created_by_id", ColType::Int),
        ],
        search: &["title", "email_subject"],
        default_order: "-created_at",
    });
}
