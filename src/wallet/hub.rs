//! Balance-push fan-out.
//! Mirrors the Channels group `wallet_user_{id}` used by
//! `Wallet._push_balance_update`: every credit/debit publishes a
//! `balance_update` payload; open websocket connections subscribe.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use super::models::WalletBalances;

#[derive(Clone, Default)]
pub struct WalletHub {
    inner: Arc<Mutex<HashMap<i64, tokio::sync::broadcast::Sender<String>>>>,
}

impl WalletHub {
    pub fn subscribe(&self, user_id: i64) -> tokio::sync::broadcast::Receiver<String> {
        let mut map = self.inner.lock().unwrap();
        map.entry(user_id)
            .or_insert_with(|| tokio::sync::broadcast::channel(64).0)
            .subscribe()
    }

    fn publish(&self, user_id: i64, message: String) {
        if let Some(tx) = self.inner.lock().unwrap().get(&user_id) {
            let _ = tx.send(message);
        }
    }

    /// Emit the `balance_update` event with the same keys Django's
    /// `wallet_update` handler forwards to the socket.
    /// `amount_display` is the decimal amount string (full precision).
    pub fn publish_update(
        &self,
        user_id: i64,
        balances: &WalletBalances,
        amount_display: &str,
        reference: &str,
        description: &str,
        transaction_type: &str,
    ) {
        let payload = serde_json::json!({
            "type": "balance_update",
            "balance": balances.balance,
            "balance_formatted": balances.balance_formatted,
            "locked_balance": balances.locked_balance,
            "locked_balance_formatted": balances.locked_balance_formatted,
            "available_balance": balances.available_balance,
            "available_balance_formatted": balances.available_balance_formatted,
            "amount": amount_display,
            "reference": reference,
            "description": description,
            "transaction_type": transaction_type,
        });
        self.publish(user_id, payload.to_string());
    }
}
