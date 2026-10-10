//! Admin models for `group_payment`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "group_payment.Group",
        label: "Group",
        table: "group_payment_group",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("name", ColType::Text),
        ("description", ColType::Text),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("created_by_id", ColType::Int),
        ("invite_members", ColType::Text),
        ("plan", ColType::Text),
        ("plan_type", ColType::Text),
        ("service_type", ColType::Text),
        ("sub_number", ColType::Text),
        ("target_amount", ColType::Int),
        ("active", ColType::Bool),
        ("current_amount", ColType::Int),
        ("status", ColType::Text),
        ("join_code", ColType::Text),
        ],
        search: &["name", "join_code"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "group_payment.GroupMember",
        label: "Group Member",
        table: "group_payment_groupmember",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("role", ColType::Text),
        ("joined_at", ColType::DateTime),
        ("group_id", ColType::Uuid),
        ("user_id", ColType::Int),
        ("locked_amount", ColType::Int),
        ("paid_amount", ColType::Int),
        ("payment_status", ColType::Text),
        ],
        search: &[],
        default_order: "-id",
    });
}
