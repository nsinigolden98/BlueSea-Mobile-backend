//! Admin models for `user_preference`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "user_preference.UpdateUserModel",
        label: "Update User Model",
        table: "user_preference_updateusermodel",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("image", ColType::Text),
        ("user_id", ColType::Int),
        ("date_of_birth", ColType::Date),
        ("country", ColType::Text),
        ("state", ColType::Text),
        ("city", ColType::Text),
        ("street_address", ColType::Text),
        ("landmark", ColType::Text),
        ("postal_code", ColType::Text),
        ("gender", ColType::Text),
        ("nickname", ColType::Text),
        ("updated_on", ColType::DateTime),
        ],
        search: &["postal_code", "nickname"],
        default_order: "-id",
    });
}
