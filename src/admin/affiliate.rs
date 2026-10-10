//! Admin models for `affiliate`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "affiliate.AffiliateLink",
        label: "Affiliate Link",
        table: "affiliate_affiliatelink",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("commission_rate", ColType::Numeric),
        ("clicks", ColType::Int),
        ("is_active", ColType::Bool),
        ("created_at", ColType::DateTime),
        ("event_id", ColType::Uuid),
        ("affiliate_id", ColType::Int),
        ],
        search: &[],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "affiliate.AffiliateProfile",
        label: "Affiliate Profile",
        table: "affiliate_affiliateprofile",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("affiliate_name", ColType::Text),
        ("status", ColType::Text),
        ("commission_rate", ColType::Numeric),
        ("facebook", ColType::Text),
        ("instagram", ColType::Text),
        ("twitter", ColType::Text),
        ("tiktok", ColType::Text),
        ("agreement_accepted", ColType::Bool),
        ("rejected_reason", ColType::Text),
        ("created_at", ColType::DateTime),
        ("updated_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ],
        search: &["affiliate_name"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "affiliate.AffiliateSale",
        label: "Affiliate Sale",
        table: "affiliate_affiliatesale",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("ticket_count", ColType::Int),
        ("gross_amount", ColType::Numeric),
        ("commission_rate", ColType::Numeric),
        ("commission_amount", ColType::Numeric),
        ("status", ColType::Text),
        ("created_at", ColType::DateTime),
        ("payable_at", ColType::DateTime),
        ("paid_at", ColType::DateTime),
        ("revoked_at", ColType::DateTime),
        ("affiliate_id", ColType::Int),
        ("buyer_id", ColType::Int),
        ("event_id", ColType::Uuid),
        ("issued_ticket_id", ColType::Uuid),
        ("link_id", ColType::Int),
        ],
        search: &[],
        default_order: "-created_at",
    });
}
