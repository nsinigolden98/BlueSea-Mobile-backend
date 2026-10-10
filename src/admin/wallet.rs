//! Admin models for `wallet`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "wallet.Wallet",
        label: "Wallet",
        table: "wallet_wallet",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("balance", ColType::Numeric),
        ("locked_balance", ColType::Numeric),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("is_active", ColType::Bool),
        ("user_id", ColType::Int),
        ],
        search: &[],
        default_order: "-created_at",
    });
}
