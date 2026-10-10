//! Response shapes for the wallet app.
//! Mirrors `wallet/serializers.py::WalletSerializer`.

use serde::Serialize;
use utoipa::ToSchema;

use super::models::Wallet;

#[derive(Debug, Serialize, ToSchema)]
pub struct WalletPublic {
    pub id: i64,
    pub user: i64,
    pub balance: String,
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
    pub is_active: bool,
}

impl From<&Wallet> for WalletPublic {
    fn from(w: &Wallet) -> Self {
        Self {
            id: w.id,
            user: w.user_id,
            balance: w.balance.clone(),
            created_at: w.created_at.0,
            updated_at: w.updated_at.0,
            is_active: w.is_active,
        }
    }
}
