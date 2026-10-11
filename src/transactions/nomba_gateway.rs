//! Nomba API client. Mirrors `transactions/nomba_gateway.py`, rebuilt on the
//! async `nomba-rs` SDK (`AsyncNomba`, everything `.await`ed — no blocking
//! calls anywhere in the request path).
//!
//! Return shapes mirror the Django helpers: `(bool, String)` for
//! create-style calls (payload or error message), `{"success", ...}` values
//! for lookups, `(bool, Value)` for calls whose data the views persist.

use std::collections::HashMap;

use nomba_rs::{AsyncNomba, NombaError};

use crate::settings::Config;

fn err_msg(e: &NombaError) -> String {
    // Mirrors Django's `_err` (API status/code prefix, else plain message).
    match e {
        NombaError::Api { status_code, code, message, .. } => {
            let status = status_code.map(|s| s.to_string()).unwrap_or_default();
            let code = code.as_deref().unwrap_or(message);
            format!("Nomba error {status}: {code}")
        }
        _ => e.to_string(),
    }
}

pub async fn client(config: &Config) -> Result<AsyncNomba, NombaError> {
    // Mirrors `sandbox=settings.NOMBA_DEBUG` (NOMBA_SANDBOX defaults to DEBUG).
    if config.nomba_sandbox {
        AsyncNomba::new_sandbox(
            config.nomba_client_id.clone(),
            config.nomba_secret_key.clone(),
            config.nomba_account_id.clone(),
        )
        .await
    } else {
        AsyncNomba::new(
            config.nomba_client_id.clone(),
            config.nomba_secret_key.clone(),
            config.nomba_account_id.clone(),
        )
        .await
    }
}

fn data_value<T: serde::Serialize>(resp: &T) -> serde_json::Value {
    serde_json::to_value(resp).unwrap_or(serde_json::Value::Null)
}

fn data_field(resp_value: &serde_json::Value, field: &str) -> Option<String> {
    resp_value
        .get("data")
        .and_then(|d| d.get(field))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

/// Hosted checkout order. Returns `(True, checkout_link)` or `(False, message)`.
pub async fn create_checkout_order(
    config: &Config,
    order_reference: &str,
    amount_cents: i64,
    email: &str,
) -> (bool, String) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, err_msg(&e)),
    };
    // The Rust SDK requires customer name + redirect URL, which Django's
    // call omits; the customer email and site URL are the closest equivalents.
    let amount = format!("{:.2}", amount_cents as f64 / 100.0);
    let resp = client
        .checkout
        .create_order(
            order_reference,
            amount,
            "NGN",
            email,
            email,
            config.site_url.clone(),
            None,
            None,
        )
        .await;
    match resp {
        Err(e) => {
            tracing::warn!("nomba checkout order failed for {order_reference}: {e}");
            (false, err_msg(&e))
        }
        Ok(r) => {
            let v = data_value(&r);
            match data_field(&v, "checkoutLink") {
                Some(link) => (true, link),
                None => {
                    tracing::warn!("nomba checkout bad shape for {order_reference}: {v}");
                    (false, "Unexpected checkout response".to_string())
                }
            }
        }
    }
}

/// Bank account lookup. Returns `{"success", "account_name"/"message"}`.
pub async fn lookup_account_name(
    config: &Config,
    account_number: &str,
    bank_code: &str,
) -> serde_json::Value {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => {
            return serde_json::json!({"success": false, "message": err_msg(&e)});
        }
    };
    match client.transfers.bank_account_lookup(account_number, bank_code).await {
        Err(e) => serde_json::json!({"success": false, "message": err_msg(&e)}),
        Ok(r) => {
            let v = data_value(&r);
            match data_field(&v, "accountName") {
                Some(name) => serde_json::json!({"success": true, "account_name": name}),
                None => serde_json::json!({"success": false, "message": "Could not resolve account name"}),
            }
        }
    }
}

/// Dedicated virtual account. Returns `(True, data)` or `(False, message)`.
pub async fn create_virtual_account(
    config: &Config,
    account_ref: &str,
    account_name: &str,
    nin: Option<String>,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    match client
        .virtual_accounts
        .create_virtual_account(account_ref, account_name, None, nin, None, None)
        .await
    {
        Err(e) => {
            tracing::warn!("nomba virtual account failed for {account_ref}: {e}");
            (false, serde_json::Value::String(err_msg(&e)))
        }
        Ok(r) => {
            let v = data_value(&r);
            if v.get("data").is_some() {
                (true, v.get("data").cloned().unwrap_or(serde_json::Value::Null))
            } else {
                (false, serde_json::Value::String("Unexpected virtual account response".to_string()))
            }
        }
    }
}

/// Parent-account bank transfer. Returns `(True, data)` or `(False, message)`.
pub async fn transfer_to_bank(
    config: &Config,
    amount_cents: i64,
    account_number: &str,
    account_name: &str,
    bank_code: &str,
    merchant_tx_ref: &str,
    sender_name: Option<String>,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    let amount = format!("{:.2}", amount_cents as f64 / 100.0);
    match client
        .transfers
        .bank_transfer_from_parent(
            amount,
            account_number,
            bank_code,
            account_name,
            merchant_tx_ref,
            sender_name,
        )
        .await
    {
        Err(e) => {
            tracing::warn!("nomba transfer failed for {merchant_tx_ref}: {e}");
            (false, serde_json::Value::String(err_msg(&e)))
        }
        Ok(r) => {
            let v = data_value(&r);
            if v.get("data").is_some() {
                (true, v.get("data").cloned().unwrap_or(serde_json::Value::Null))
            } else {
                (false, serde_json::Value::String("Unexpected transfer response".to_string()))
            }
        }
    }
}

/// Reconfirm a transaction by sessionId. Returns `(True, data)` or `(False, message)`.
pub async fn confirm_transaction(
    config: &Config,
    session_id: &str,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    match client.transactions.confirm_by_session_id(session_id).await {
        Err(e) => (false, serde_json::Value::String(err_msg(&e))),
        Ok(r) => {
            let v = data_value(&r);
            if v.get("data").is_some() {
                (true, v.get("data").cloned().unwrap_or(serde_json::Value::Null))
            } else {
                (false, serde_json::Value::String("Unexpected transaction response".to_string()))
            }
        }
    }
}

/// Nomba success envelope: every bill response carries `code == "00"`.
pub fn is_success(v: &serde_json::Value) -> bool {
    v.get("code").and_then(|c| c.as_str()) == Some("00")
}

/// Generic vend/lookup helper returning `(true, data)` or `(false, message)`.
async fn vend_call<F, T>(label: &str, tx_ref: &str, fut: F) -> (bool, serde_json::Value)
where
    F: std::future::Future<Output = Result<T, NombaError>>,
    T: serde::Serialize,
{
    match fut.await {
        Err(e) => {
            tracing::warn!("nomba {label} failed for {tx_ref}: {e}");
            (false, serde_json::Value::String(err_msg(&e)))
        }
        Ok(r) => {
            let v = data_value(&r);
            if is_success(&v) {
                (true, v.get("data").cloned().unwrap_or(serde_json::Value::Null))
            } else {
                let msg = v
                    .get("description")
                    .and_then(|d| d.as_str())
                    .unwrap_or("Nomba request failed")
                    .to_string();
                (false, serde_json::Value::String(msg))
            }
        }
    }
}

/// Airtime top-up via parent account.
pub async fn purchase_airtime(
    config: &Config,
    amount_naira: i64,
    phone: &str,
    network: &str,
    merchant_tx_ref: &str,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    vend_call("airtime", merchant_tx_ref, client.airtime_data.purchase_airtime_parent(
        amount_naira as f64, phone, network, merchant_tx_ref, None,
    )).await
}

/// Data vending via parent account. `product_id` is the Nomba plan id from
/// the plans cache (`/ws/plans/`).
pub async fn vend_data(
    config: &Config,
    product_id: &str,
    phone: &str,
    network: &str,
    merchant_tx_ref: &str,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    vend_call("data", merchant_tx_ref, client.airtime_data.vend_data_parent(
        product_id, phone, network, merchant_tx_ref, None,
    )).await
}

/// Cable subscription via parent account.
pub async fn subscribe_cable(
    config: &Config,
    provider: &str,
    smart_card: &str,
    plan: &str,
    amount_naira: i64,
    merchant_tx_ref: &str,
    phone: Option<String>,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    vend_call("cable", merchant_tx_ref, client.cabletv.subscribe_parent(
        provider, smart_card, plan, amount_naira as f64, merchant_tx_ref, phone,
    )).await
}

/// Electricity vending via parent account.
pub async fn vend_electricity(
    config: &Config,
    provider: &str,
    meter: &str,
    amount_naira: i64,
    merchant_tx_ref: &str,
    phone: Option<String>,
    meter_type: Option<String>,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    vend_call("electricity", merchant_tx_ref, client.electricity.vend_parent(
        provider, meter, amount_naira as f64, merchant_tx_ref, phone, meter_type,
    )).await
}

/// Betting-account funding via parent account (fund only — no bet placement).
pub async fn fund_betting(
    config: &Config,
    provider: &str,
    customer_id: &str,
    amount_naira: i64,
    merchant_tx_ref: &str,
    phone: Option<String>,
) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    vend_call("betting", merchant_tx_ref, client.betting.vend_parent(
        provider, customer_id, amount_naira as f64, merchant_tx_ref, phone,
    )).await
}

/// Electricity discos list. Returns `(true, data)` or `(false, message)`.
pub async fn fetch_electricity_providers(config: &Config) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    match client.electricity.fetch_providers().await {
        Err(e) => (false, serde_json::Value::String(err_msg(&e))),
        Ok(r) => (true, data_value(&r)),
    }
}

/// Electricity customer lookup. Returns `{"success", ...}` like account-name.
pub async fn lookup_electricity_customer(
    config: &Config,
    provider: &str,
    meter: &str,
) -> serde_json::Value {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return serde_json::json!({"success": false, "message": err_msg(&e)}),
    };
    match client.electricity.customer_lookup(provider, meter).await {
        Err(e) => serde_json::json!({"success": false, "message": err_msg(&e)}),
        Ok(r) => {
            let v = data_value(&r);
            if is_success(&v) {
                serde_json::json!({"success": true, "customer": v.get("data").cloned().unwrap_or(serde_json::Value::Null)})
            } else {
                serde_json::json!({"success": false, "message": v.get("description").and_then(|d| d.as_str()).unwrap_or("Lookup failed")})
            }
        }
    }
}

/// Betting providers list.
pub async fn fetch_betting_providers(config: &Config) -> (bool, serde_json::Value) {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return (false, serde_json::Value::String(err_msg(&e))),
    };
    match client.betting.fetch_providers().await {
        Err(e) => (false, serde_json::Value::String(err_msg(&e))),
        Ok(r) => (true, data_value(&r)),
    }
}

/// Betting customer lookup.
pub async fn lookup_betting_customer(
    config: &Config,
    provider: &str,
    customer_id: &str,
) -> serde_json::Value {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return serde_json::json!({"success": false, "message": err_msg(&e)}),
    };
    match client.betting.customer_lookup(provider, customer_id).await {
        Err(e) => serde_json::json!({"success": false, "message": err_msg(&e)}),
        Ok(r) => {
            let v = data_value(&r);
            if is_success(&v) {
                serde_json::json!({"success": true, "customer": v.get("data").cloned().unwrap_or(serde_json::Value::Null)})
            } else {
                serde_json::json!({"success": false, "message": v.get("description").and_then(|d| d.as_str()).unwrap_or("Lookup failed")})
            }
        }
    }
}

/// Cable customer (smart-card) lookup.
pub async fn lookup_cable_customer(
    config: &Config,
    provider: &str,
    smart_card: &str,
) -> serde_json::Value {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => return serde_json::json!({"success": false, "message": err_msg(&e)}),
    };
    match client.cabletv.lookup(provider, smart_card).await {
        Err(e) => serde_json::json!({"success": false, "message": err_msg(&e)}),
        Ok(r) => {
            let v = data_value(&r);
            if is_success(&v) {
                serde_json::json!({"success": true, "customer": v.get("data").cloned().unwrap_or(serde_json::Value::Null)})
            } else {
                serde_json::json!({"success": false, "message": v.get("description").and_then(|d| d.as_str()).unwrap_or("Lookup failed")})
            }
        }
    }
}

/// Raw data plans for one network (cached by the plans store at startup).
/// Every failure point logs the underlying cause — a bare "unavailable"
/// cost an evening of probing against a deserialization mismatch.
pub async fn fetch_data_plans_raw(config: &Config, network: &str) -> Option<serde_json::Value> {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => {
            tracing::warn!("nomba data plans: client build failed for {network}: {e}");
            return None;
        }
    };
    match client.airtime_data.fetch_data_plans(network).await {
        Err(e) => {
            tracing::warn!("nomba data plans: fetch failed for {network}: {e}");
            None
        }
        Ok(r) => {
            let v = data_value(&r);
            if is_success(&v) {
                Some(v.get("data").cloned().unwrap_or(serde_json::Value::Null))
            } else {
                tracing::warn!(
                    "nomba data plans: non-success payload for {network}: code={} description={}",
                    v.get("code").and_then(|c| c.as_str()).unwrap_or("?"),
                    v.get("description").and_then(|d| d.as_str()).unwrap_or("?"),
                );
                None
            }
        }
    }
}

/// Raw cable plans for one provider (cached by the plans store at startup).
/// Same loud-failure contract as [`fetch_data_plans_raw`].
pub async fn fetch_cable_plans_raw(config: &Config, provider: &str) -> Option<serde_json::Value> {
    let client = match client(config).await {
        Ok(c) => c,
        Err(e) => {
            tracing::warn!("nomba cable plans: client build failed for {provider}: {e}");
            return None;
        }
    };
    match client.cabletv.fetch_plans(provider).await {
        Err(e) => {
            tracing::warn!("nomba cable plans: fetch failed for {provider}: {e}");
            None
        }
        Ok(r) => {
            let v = data_value(&r);
            if is_success(&v) {
                Some(v.get("data").cloned().unwrap_or(serde_json::Value::Null))
            } else {
                tracing::warn!(
                    "nomba cable plans: non-success payload for {provider}: code={} description={}",
                    v.get("code").and_then(|c| c.as_str()).unwrap_or("?"),
                    v.get("description").and_then(|d| d.as_str()).unwrap_or("?"),
                );
                None
            }
        }
    }
}
/// Webhook timestamp age in seconds. Tolerant of `Z` and numeric offsets
/// (with or without millis). Returns `None` when unparseable.
fn webhook_timestamp_age(ts: &str) -> Option<i64> {
    let t = ts.trim();
    // chrono rejects the space the SDK inserts after stripping `Z`;
    // normalize `Z` to `+00:00` ourselves instead.
    let norm = match t.strip_suffix(['Z', 'z']) {
        Some(s) => format!("{s}+00:00"),
        None => t.to_string(),
    };
    chrono::DateTime::parse_from_rfc3339(&norm)
        .ok()
        .map(|d| (chrono::Utc::now() - d.with_timezone(&chrono::Utc)).num_seconds())
}

/// Verify an inbound webhook. Returns the payload, or an error message
/// (mirroring Django's "Invalid signature" / "Verification failed" split).
pub fn verify_webhook(
    signature_key: &str,
    body: &[u8],
    headers: &axum::http::HeaderMap,
) -> Result<serde_json::Value, String> {
    if body.len() > 1024 * 100 {
        tracing::warn!("nomba webhook payload too large {}", body.len());
        // Django acks oversized payloads without processing; signal that
        // with a marker the handler turns into {"success": true}.
        return Err("__too_large__".to_string());
    }
    // 5-minute freshness window: captured webhooks can't be replayed later.
    // (Handlers are idempotent too — this is defense in depth.)
    // NOTE: enforced here, not via the SDK's `max_age_seconds`: nomba-rs
    // 0.2.0's freshness parser rejects `Z`-suffixed timestamps outright,
    // which would 401 every real webhook.
    const MAX_AGE: i64 = 300;
    match headers
        .get("nomba-timestamp")
        .and_then(|v| v.to_str().ok())
        .map(webhook_timestamp_age)
    {
        None => return Err("Invalid signature".to_string()),
        Some(None) => return Err("Invalid signature".to_string()),
        Some(Some(age)) if age.abs() > MAX_AGE => {
            tracing::warn!("stale nomba webhook (age {age}s, possible replay)");
            return Err("Invalid signature".to_string());
        }
        Some(Some(_)) => {}
    }
    let map: HashMap<String, String> = headers
        .iter()
        .filter_map(|(k, v)| v.to_str().ok().map(|s| (k.as_str().to_string(), s.to_string())))
        .collect();
    nomba_rs::verify_webhook_request(signature_key, body, &map, None).map_err(|e| {
        match e {
            NombaError::Validation { .. } => "Invalid signature".to_string(),
            _ => "Verification failed".to_string(),
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn timestamp_age_accepts_z_and_offsets() {
        let now_z = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        let age = webhook_timestamp_age(&now_z).expect("Z parses");
        assert!(age.abs() <= 5, "age {age}");
        let now_off = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, false);
        let age = webhook_timestamp_age(&now_off).expect("offset+millis parses");
        assert!(age.abs() <= 5, "age {age}");
        // Stale and garbage.
        assert!(webhook_timestamp_age("2020-01-01T00:00:00Z").unwrap() > 300);
        assert!(webhook_timestamp_age("not-a-time").is_none());
    }
}
