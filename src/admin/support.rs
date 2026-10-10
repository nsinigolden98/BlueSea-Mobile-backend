//! Admin models for `support`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "support.SupportAttachment",
        label: "Support Attachment",
        table: "support_supportattachment",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("image", ColType::Text),
        ("uploaded_at", ColType::DateTime),
        ("message_id", ColType::Int),
        ],
        search: &[],
        default_order: "-id",
    });
    out.push(ModelDef {
        name: "support.SupportMessage",
        label: "Support Message",
        table: "support_supportmessage",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("message", ColType::Text),
        ("is_admin", ColType::Bool),
        ("created_at", ColType::DateTime),
        ("sender_id", ColType::Int),
        ("ticket_id", ColType::Int),
        ],
        search: &[],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "support.SupportTicket",
        label: "Support Ticket",
        table: "support_supportticket",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("subject", ColType::Text),
        ("description", ColType::Text),
        ("status", ColType::Text),
        ("priority", ColType::Text),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ],
        search: &["subject"],
        default_order: "-created_at",
    });
}
