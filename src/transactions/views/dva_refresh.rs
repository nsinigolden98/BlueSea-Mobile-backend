//! DVA requery. Mirrors `transactions/views.py::DvaRefreshView`:
//! Paystack `dedicated_account/requery` for Wema, rate-limited to once per
//! 10 minutes per DVA (in-process store, like Django's cache usage).

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::json;

use crate::accounts::models as accounts_models;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::transactions::paystack;
use crate::transactions::serializers::DvaRefreshBody;

static REQUERY_LIMIT: OnceLock<Mutex<HashMap<String, i64>>> = OnceLock::new();

fn requery_limited(account_number: &str) -> bool {
    let now = chrono::Utc::now().timestamp();
    let map = REQUERY_LIMIT
        .get_or_init(|| Mutex::new(HashMap::new()))
        .lock()
        .unwrap();
    if map.get(account_number).map(|exp| *exp > now).unwrap_or(false) {
        return true;
    }
    false
}

fn mark_requeried(account_number: &str) {
    let exp = chrono::Utc::now().timestamp() + 600;
    REQUERY_LIMIT
        .get_or_init(|| Mutex::new(HashMap::new()))
        .lock()
        .unwrap()
        .insert(account_number.to_string(), exp);
}

#[utoipa::path(
    post,
    path = "/transactions/dva/refresh/",
    tag = "Wallet & Transactions",
    summary = "Requery Wema DVA for pending transfers",
    description = "Triggers Paystack requery for the user's dedicated account. Limited to once every 10 minutes.",
    request_body = DvaRefreshBody,
    responses(
        (status = 200, description = "Requery accepted"),
        (status = 400, description = "Bad date or Paystack failure"),
        (status = 404, description = "No DVA assigned"),
        (status = 429, description = "Requery too frequent"),
    ),
    security(("bearer" = [])),
)]
pub async fn dva_refresh(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<DvaRefreshBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    let dva = accounts_models::find_dva_by_user(&s.db, user.id).await?;
    let Some(dva) = dva else {
        return Err(AppError {
            status: StatusCode::NOT_FOUND,
            message: "No DVA assigned. POST /account/dva/assign first.".into(),
        });
    };

    if requery_limited(&dva.account_number) {
        return Err(AppError {
            status: StatusCode::TOO_MANY_REQUESTS,
            message: "Requery allowed once every 10 minutes".into(),
        });
    }

    let date_str = match b.date {
        Some(d) => {
            if chrono::NaiveDate::parse_from_str(&d, "%Y-%m-%d").is_err() {
                return Err(AppError::bad_request("date must be YYYY-MM-DD"));
            }
            d
        }
        None => chrono::Utc::now().date_naive().to_string(),
    };

    let data = match paystack::requery_dva(
        &s.http,
        &s.config.paystack_secret_key,
        &dva.account_number,
        &date_str,
    )
    .await
    {
        Ok(v) => v,
        Err(e) => {
            return Err(AppError {
                status: StatusCode::BAD_GATEWAY,
                message: e.into(),
            })
        }
    };

    let status_ok = data.get("status").and_then(|v| v.as_bool()) == Some(true);
    let message = data
        .get("message")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    if !status_ok {
        if message.contains("10 minutes") || message.to_lowercase().contains("10 minute") {
            mark_requeried(&dva.account_number);
            return Ok((
                StatusCode::TOO_MANY_REQUESTS,
                Json(json!({
                    "error": message,
                    "paystack_status": data.get("status"),
                    "paystack_message": message,
                })),
            ));
        }
        tracing::warn!("DVA requery failed for {}: {data}", user.email);
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error": if message.is_empty() { "Failed to requery dedicated account".to_string() } else { message.clone() },
                "paystack_status": data.get("status"),
                "paystack_message": message,
            })),
        ));
    }

    mark_requeried(&dva.account_number);
    tracing::info!(
        "DVA requery success for {} account {} date {date_str}: {data}",
        user.email,
        dva.account_number
    );
    Ok((
        StatusCode::OK,
        Json(json!({
            "status": data.get("status"),
            "message": message,
            "account_number": dva.account_number,
            "provider_slug": "wema-bank",
            "date": date_str,
            "requery": true,
        })),
    ))
}
