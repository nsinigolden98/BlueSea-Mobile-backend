//! Admin models for `autotopup`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "autotopup.AutoTopUp",
        label: "Auto Top Up",
        table: "autotopup_autotopup",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("service_type", ColType::Text),
        ("amount", ColType::Numeric),
        ("phone_number", ColType::Text),
        ("network", ColType::Text),
        ("plan", ColType::Text),
        ("start_date", ColType::DateTime),
        ("repeat_days", ColType::Int),
        ("is_active", ColType::Bool),
        ("next_run", ColType::DateTime),
        ("is_locked", ColType::Bool),
        ("locked_amount", ColType::Numeric),
        ("last_run", ColType::DateTime),
        ("total_runs", ColType::Int),
        ("failed_runs", ColType::Int),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ],
        search: &["phone_number"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "autotopup.AutoTopUpHistory",
        label: "Auto Top Up History",
        table: "autotopup_autotopuphistory",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("amount", ColType::Numeric),
        ("status", ColType::Text),
        ("vtu_reference", ColType::Text),
        ("vtu_response", ColType::Json),
        ("error_message", ColType::Text),
        ("executed_at", ColType::DateTime),
        ("auto_topup_id", ColType::Int),
        ],
        search: &["vtu_reference"],
        default_order: "-id",
    });
}
