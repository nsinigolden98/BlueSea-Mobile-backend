//! Admin models for `loyalty_market`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "loyalty_market.RedemptionTransaction",
        label: "Redemption Transaction",
        table: "loyalty_market_redemptiontransaction",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("points_deducted", ColType::Int),
        ("status", ColType::Text),
        ("created_at", ColType::DateTime),
        ("redeemed_at", ColType::DateTime),
        ("fulfilment_payload", ColType::Json),
        ("user_id_id", ColType::Int),
        ("reward_id_id", ColType::Uuid),
        ],
        search: &[],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "loyalty_market.Reward",
        label: "Reward",
        table: "loyalty_market_reward",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("title", ColType::Text),
        ("description", ColType::Text),
        ("image_url", ColType::Text),
        ("points_cost", ColType::Int),
        ("category", ColType::Text),
        ("inventory", ColType::Int),
        ("availability_start", ColType::DateTime),
        ("availability_end", ColType::DateTime),
        ("fulfilment_type", ColType::Text),
        ("polarity_score", ColType::Int),
        ("created_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ],
        search: &["title"],
        default_order: "-created_at",
    });
}
