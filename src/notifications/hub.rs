//! Live notification fan-out. Mirrors the wallet hub pattern: every
//! in-app notification row published here is pushed to that user's open
//! `/ws/notifications/` socket (no-op when nobody listens).

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

#[derive(Clone, Default)]
pub struct NotificationHub {
    inner: Arc<Mutex<HashMap<i64, tokio::sync::broadcast::Sender<String>>>>,
}

impl NotificationHub {
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

    /// Emit a `new_notification` event for a freshly stored row.
    /// `created_at` is the display string already rendered for the row.
    pub fn publish_notification(
        &self,
        user_id: i64,
        id: i64,
        title: &str,
        message: &str,
        notification_type: &str,
        created_at: &str,
    ) {
        let payload = serde_json::json!({
            "type": "new_notification",
            "id": id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "created_at": created_at,
        });
        self.publish(user_id, payload.to_string());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn publish_reaches_only_subscribed_user() {
        let hub = NotificationHub::default();
        let mut rx1 = hub.subscribe(1);
        let mut rx2 = hub.subscribe(2);
        hub.publish_notification(1, 10, "T", "M", "info", "now");
        let msg = tokio::time::timeout(std::time::Duration::from_secs(1), rx1.recv())
            .await
            .expect("user 1 gets the push")
            .unwrap();
        assert!(msg.contains("new_notification") && msg.contains("\"id\":10"));
        // User 2 gets nothing.
        assert!(tokio::time::timeout(std::time::Duration::from_millis(100), rx2.recv())
            .await
            .is_err());
    }
}
