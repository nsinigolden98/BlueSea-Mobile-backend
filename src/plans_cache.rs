//! Startup-cached Nomba plans store + `/ws/plans/` socket.
//!
//! At boot the server fetches data plans (4 networks) and cable plans
//! (4 providers) via `nomba-rs` in parallel and caches them in-process.
//! A background task refreshes the cache every 6 hours; if Nomba is
//! unreachable at boot the server still starts with an empty cache and
//! keys report `plans unavailable` until a refresh succeeds.
//!
//! Socket protocol (JWT via `?token=` / `?access=` / `Authorization: Bearer`,
//! same semantics as the wallet socket, close code 4401 when unauthenticated):
//! - client `{"type": "get_plans", "key": "dstv"}` → server
//!   `{"type": "plans", "key": "dstv", "kind": "cable", "plans": [...],
//!   "updated_at": ...}`
//! - client `{"type": "get_all"}` → all 8 keys at once.
//! - unknown key → `{"type": "error", "detail": ...}`; `ping` → `pong`.
//!
//! Keys: `mtn|airtel|glo|9mobile|dstv|gotv|showmax|startimes`.

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use axum::{
    Router,
    extract::{
        Query, State,
        ws::{CloseFrame, Message, WebSocket, WebSocketUpgrade},
    },
    http::HeaderMap,
    response::IntoResponse,
    routing::get,
};
use serde_json::{Value, json};

use crate::auth::extractor::get_profile;
use crate::auth::jwt as auth_jwt;
use crate::settings::Config;
use crate::state::AppState;
use crate::transactions::nomba_gateway;

/// (Nomba fetch id, cache key, kind).
const DATA_NETWORKS: &[(&str, &str)] = &[
    ("MTN", "mtn"),
    ("AIRTEL", "airtel"),
    ("GLO", "glo"),
    ("9MOBILE", "9mobile"),
];
const CABLE_PROVIDERS: &[(&str, &str)] = &[
    ("DSTV", "dstv"),
    ("GOTV", "gotv"),
    ("STARTIMES", "startimes"),
    ("SHOWMAX", "showmax"),
];

#[derive(Clone, Debug)]
pub struct CachedPlans {
    pub kind: &'static str,
    pub updated_at: String,
    pub plans: Value,
}

#[derive(Clone, Default, Debug)]
pub struct PlansStore {
    inner: Arc<RwLock<HashMap<String, CachedPlans>>>,
}

impl PlansStore {
    pub fn get(&self, key: &str) -> Option<CachedPlans> {
        self.inner.read().ok()?.get(key).cloned()
    }

    pub fn keys(&self) -> Vec<String> {
        self.inner.read().map(|m| m.keys().cloned().collect()).unwrap_or_default()
    }

    fn insert(&self, key: String, entry: CachedPlans) {
        if let Ok(mut m) = self.inner.write() {
            m.insert(key, entry);
        }
    }

    /// Fetch all 8 plan lists in parallel. Failures are logged and leave
    /// any previously cached value in place (empty on first boot).
    pub async fn warm(&self, config: &Config) {
        let (d0, d1, d2, d3) = (
            nomba_gateway::fetch_data_plans_raw(config, DATA_NETWORKS[0].0),
            nomba_gateway::fetch_data_plans_raw(config, DATA_NETWORKS[1].0),
            nomba_gateway::fetch_data_plans_raw(config, DATA_NETWORKS[2].0),
            nomba_gateway::fetch_data_plans_raw(config, DATA_NETWORKS[3].0),
        );
        let (c0, c1, c2, c3) = (
            nomba_gateway::fetch_cable_plans_raw(config, CABLE_PROVIDERS[0].0),
            nomba_gateway::fetch_cable_plans_raw(config, CABLE_PROVIDERS[1].0),
            nomba_gateway::fetch_cable_plans_raw(config, CABLE_PROVIDERS[2].0),
            nomba_gateway::fetch_cable_plans_raw(config, CABLE_PROVIDERS[3].0),
        );
        let (d0, d1, d2, d3, c0, c1, c2, c3) =
            tokio::join!(d0, d1, d2, d3, c0, c1, c2, c3);
        let now = crate::time::now_str();
        let data = [d0, d1, d2, d3];
        for (i, (_, key)) in DATA_NETWORKS.iter().enumerate() {
            match &data[i] {
                Some(plans) => self.insert(key.to_string(), CachedPlans {
                    kind: "data", updated_at: now.clone(), plans: plans.clone(),
                }),
                None => tracing::warn!("plans cache: data plans unavailable for {key}"),
            }
        }
        let cable = [c0, c1, c2, c3];
        for (i, (_, key)) in CABLE_PROVIDERS.iter().enumerate() {
            match &cable[i] {
                Some(plans) => self.insert(key.to_string(), CachedPlans {
                    kind: "cable", updated_at: now.clone(), plans: plans.clone(),
                }),
                None => tracing::warn!("plans cache: cable plans unavailable for {key}"),
            }
        }
    }
}

/// Best-effort price lookup for a Nomba data product id. Nomba plan objects
/// vary; match common id keys and read common price keys (naira).
fn find_price(plans: &Value, product_id: &str) -> Option<i64> {
    let arr = match plans {
        Value::Array(a) => a.clone(),
        Value::Object(m) => {
            // Some responses wrap the list in `plans`/`data`/`products`.
            ["plans", "data", "products", "items"]
                .iter()
                .find_map(|k| m.get(*k).and_then(|v| v.as_array()).cloned())
                .unwrap_or_default()
        }
        _ => return None,
    };
    for item in &arr {
        let id_match = ["productId", "product_id", "id", "planId", "plan_id", "code", "planCode"]
            .iter()
            .any(|k| item.get(*k).and_then(|v| v.as_str()) == Some(product_id));
        if !id_match {
            continue;
        }
        for k in ["amount", "price", "priceNGN", "nairaPrice", "fee"] {
            if let Some(v) = item.get(k) {
                let n = match v {
                    Value::Number(n) => n.as_f64(),
                    Value::String(s) => s.trim().parse::<f64>().ok(),
                    _ => None,
                };
                if let Some(n) = n {
                    return Some(n.round() as i64);
                }
            }
        }
        return None;
    }
    None
}

/// Cached naira price for a data product, if the cache has it.
pub fn data_price(store: &PlansStore, key: &str, product_id: &str) -> Option<i64> {
    store.get(key).and_then(|c| find_price(&c.plans, product_id))
}

/// Cached naira price for a cable plan, if the cache has it.
pub fn cable_price(store: &PlansStore, key: &str, plan_id: &str) -> Option<i64> {
    store.get(key).and_then(|c| find_price(&c.plans, plan_id))
}

// ---------- websocket ----------

async fn authed_user_id(state: &AppState, params: &HashMap<String, String>, headers: &HeaderMap) -> Option<i64> {
    let mut token = params
        .get("token")
        .or_else(|| params.get("access"))
        .cloned()
        .unwrap_or_default();
    if token.is_empty() {
        if let Some(h) = headers.get("authorization").and_then(|v| v.to_str().ok()) {
            if h.len() > 7 && h[..7].eq_ignore_ascii_case("bearer ") {
                token = h[7..].to_string();
            }
        }
    }
    if token.is_empty() {
        return None;
    }
    let claims = auth_jwt::decode_claims(&token, &state.config.secret_key).ok()?;
    if auth_jwt::is_blacklisted(&state.db, &claims.jti).await.ok()? {
        return None;
    }
    let user = get_profile(&state.db, claims.user_id).await.ok()?;
    if !user.is_active {
        return None;
    }
    Some(user.id)
}

fn plans_message(key: &str, entry: &CachedPlans) -> Value {
    json!({
        "type": "plans",
        "key": key,
        "kind": entry.kind,
        "plans": entry.plans,
        "updated_at": entry.updated_at,
    })
}

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    Query(params): Query<HashMap<String, String>>,
    headers: HeaderMap,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let user_id = authed_user_id(&state, &params, &headers).await;
    ws.on_upgrade(move |socket| handle_socket(socket, state, user_id))
}

async fn handle_socket(mut socket: WebSocket, state: AppState, user_id: Option<i64>) {
    let Some(user_id) = user_id else {
        let _ = socket
            .send(Message::Close(Some(CloseFrame { code: 4401, reason: "unauthorized".into() })))
            .await;
        return;
    };
    let hello = json!({"type": "connected", "user_id": user_id});
    if socket.send(Message::Text(hello.to_string().into())).await.is_err() {
        return;
    }
    loop {
        let Some(Ok(msg)) = socket.recv().await else { break };
        let Message::Text(text) = msg else { continue };
        let value: Value = match serde_json::from_str(text.as_str()) {
            Ok(v) => v,
            Err(_) => continue,
        };
        match value.get("type").and_then(|t| t.as_str()) {
            Some("ping") => {
                if socket.send(Message::Text(json!({"type": "pong"}).to_string().into())).await.is_err() {
                    break;
                }
            }
            Some("get_plans") => {
                let key = value.get("key").and_then(|k| k.as_str()).unwrap_or("");
                let out = match state.plans_store.get(key) {
                    Some(entry) => plans_message(key, &entry),
                    None => json!({"type": "error", "detail": "plans unavailable"}),
                };
                if socket.send(Message::Text(out.to_string().into())).await.is_err() {
                    break;
                }
            }
            Some("get_all") => {
                let mut all = serde_json::Map::new();
                for key in ["mtn", "airtel", "glo", "9mobile", "dstv", "gotv", "showmax", "startimes"] {
                    if let Some(entry) = state.plans_store.get(key) {
                        all.insert(key.to_string(), plans_message(key, &entry));
                    }
                }
                let out = json!({"type": "plans_all", "plans": all});
                if socket.send(Message::Text(out.to_string().into())).await.is_err() {
                    break;
                }
            }
            _ => {}
        }
    }
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/ws/plans/", get(ws_handler))
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn price_scan_reads_common_shapes() {
        let plans = json!([
            {"productId": "P1", "amount": 500},
            {"id": "P2", "price": "1500.00"},
        ]);
        assert_eq!(find_price(&plans, "P1"), Some(500));
        assert_eq!(find_price(&plans, "P2"), Some(1500));
        assert_eq!(find_price(&plans, "PX"), None);
    }

    #[test]
    fn missing_key_reports_none() {
        let store = PlansStore::default();
        assert!(store.get("mtn").is_none());
        assert!(data_price(&store, "mtn", "P1").is_none());
    }
}
