//! Admin models for `transactions`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "transactions.AccountName",
        label: "Account Name",
        table: "transactions_accountname",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("account_number", ColType::Int),
        ("bank_code", ColType::Int),
        ],
        search: &["bank_code"],
        default_order: "-id",
    });
    out.push(ModelDef {
        name: "transactions.FundWallet",
        label: "Fund Wallet",
        table: "transactions_fundwallet",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("amount", ColType::Numeric),
        ("payment_reference", ColType::Text),
        ("gateway_reference", ColType::Text),
        ("status", ColType::Text),
        ("created_at", ColType::DateTime),
        ("completed_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ],
        search: &["payment_reference", "gateway_reference"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "transactions.WalletTransaction",
        label: "Wallet Transaction",
        table: "transactions_wallettransaction",
        pk: "id",
        pk_type: PkType::Int,
        columns: &[
        ("id", ColType::Int),
        ("amount", ColType::Numeric),
        ("transaction_type", ColType::Text),
        ("status", ColType::Text),
        ("description", ColType::Text),
        ("reference", ColType::Text),
        ("created_at", ColType::DateTime),
        ("wallet_id", ColType::Int),
        ],
        search: &["reference"],
        default_order: "-created_at",
    });
}
