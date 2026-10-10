//! Live-chat fan-out for support.
//! Mirrors the Channels groups `support_ticket_<id>` and `support_user_<id>`
//! used by `support/consumers.py` + `support/admin_view.py`.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

#[derive(Clone, Default)]
pub struct SupportHub {
    inner: Arc<Mutex<HashMap<String, tokio::sync::broadcast::Sender<String>>>>,
}

impl SupportHub {
    pub fn subscribe(&self, group: &str) -> tokio::sync::broadcast::Receiver<String> {
        let mut map = self.inner.lock().unwrap();
        map.entry(group.to_string())
            .or_insert_with(|| tokio::sync::broadcast::channel(64).0)
            .subscribe()
    }

    pub fn publish(&self, group: &str, message: String) {
        if let Some(tx) = self.inner.lock().unwrap().get(group) {
            let _ = tx.send(message);
        }
    }

    /// Mirrors `_broadcast_ticket_event`: push to the ticket room and to the
    /// owner's personal group.
    pub fn publish_ticket_event(
        &self,
        ticket_id: i64,
        owner_id: i64,
        payload: &serde_json::Value,
    ) {
        let text = payload.to_string();
        self.publish(&format!("support_ticket_{ticket_id}"), text.clone());
        self.publish(&format!("support_user_{owner_id}"), text);
    }
}
