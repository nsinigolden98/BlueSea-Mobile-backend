//! Paystack API helpers. Mirrors `transactions/paystack.py`
//! (`checkout`, `get_account_name`, plus transfer helpers kept for the
//! payments app) with the DVA requery call used by `DvaRefreshView`.

use serde_json::Value;

const BASE_URL: &str = "https://api.paystack.co";

/// Initialize a checkout transaction. Returns `(ok, authorization_url_or_error)`.
/// Mirrors `paystack.checkout`.
pub async fn checkout(
    http: &reqwest::Client,
    secret_key: &str,
    payload: &Value,
) -> (bool, String) {
    let resp = match http
        .post(format!("{BASE_URL}/transaction/initialize"))
        .bearer_auth(secret_key)
        .json(payload)
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => {
            return (
                false,
                "An error occurred while processing the payment. Please try again later."
                    .to_string(),
            )
        }
    };
    let data: Value = match resp.json().await {
        Ok(v) => v,
        Err(_) => {
            return (
                false,
                "An error occurred while processing the payment. Please try again later."
                    .to_string(),
            )
        }
    };
    if data.get("status").and_then(|v| v.as_bool()) == Some(true) {
        let url = data
            .pointer("/data/authorization_url")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        (true, url)
    } else {
        (
            false,
            "Failed to initiate payment! Please try again later".to_string(),
        )
    }
}

/// Resolve a bank account name. Mirrors `paystack.get_account_name`.
pub async fn get_account_name(
    http: &reqwest::Client,
    secret_key: &str,
    account_number: &str,
    bank_code: &str,
) -> Value {
    let resp = match http
        .get(format!("{BASE_URL}/bank/resolve"))
        .bearer_auth(secret_key)
        .query(&[("account_number", account_number), ("bank_code", bank_code)])
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => {
            return serde_json::json!({"success": false, "message": "Network error"});
        }
    };
    if !resp.status().is_success() {
        return serde_json::json!({"success": false, "message": "Network error"});
    }
    let data: Value = match resp.json().await {
        Ok(v) => v,
        Err(_) => {
            return serde_json::json!({"success": false, "message": "Network error"});
        }
    };
    if data.get("status").and_then(|v| v.as_bool()) == Some(true) {
        let name = data
            .pointer("/data/account_name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        serde_json::json!({"success": true, "account_name": name})
    } else {
        serde_json::json!({"success": false, "message": data.get("message")})
    }
}

/// Requery a Wema DVA for pending transfers (Paystack allows once per
/// 10 minutes). Returns the decoded JSON on transport success.
pub async fn requery_dva(
    http: &reqwest::Client,
    secret_key: &str,
    account_number: &str,
    date: &str,
) -> Result<Value, String> {
    let resp = http
        .get(format!("{BASE_URL}/dedicated_account/requery"))
        .bearer_auth(secret_key)
        .query(&[
            ("account_number", account_number),
            ("provider_slug", "wema-bank"),
            ("date", date),
        ])
        .send()
        .await
        .map_err(|_| "Unable to contact Paystack, try again".to_string())?;
    resp.json::<Value>()
        .await
        .map_err(|_| "Invalid response from Paystack".to_string())
}
