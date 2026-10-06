//! Bonus endpoints. Mirrors `bonus/views.py`:
//! summary (5-minute in-process cache), history (type filter, manual slices),
//! daily-login claim (GET), campaigns (15-minute cache), referral GET + POST.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use axum::{Json, extract::{Query, State}, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;

use super::models as bonus_models;
use super::serializers::{BonusCampaignPublic, ReferralPublic};
use super::utils as bonus_utils;

type Resp = (StatusCode, Json<Value>);

static CACHE: OnceLock<Mutex<HashMap<String, (i64, Value)>>> = OnceLock::new();

fn cache_get(key: &str) -> Option<Value> {
    let map = CACHE.get_or_init(|| Mutex::new(HashMap::new())).lock().unwrap();
    if let Some((exp, v)) = map.get(key) {
        if *exp > chrono::Utc::now().timestamp() {
            return Some(v.clone());
        }
    }
    None
}

fn cache_set(key: &str, value: &Value, ttl_secs: i64) {
    CACHE
        .get_or_init(|| Mutex::new(HashMap::new()))
        .lock()
        .unwrap()
        .insert(
            key.to_string(),
            (chrono::Utc::now().timestamp() + ttl_secs, value.clone()),
        );
}

#[utoipa::path(
    get,
    path = "/bonus/summary/",
    tag = "Bonus & Rewards",
    summary = "Get bonus points summary",
    description = "Retrieve user's bonus points balance and statistics.",
    responses((status = 200, description = "Summary"), (status = 500, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn summary(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let key = format!("bonus_summary_{}", user.id);
    if let Some(cached) = cache_get(&key) {
        return Ok((
            StatusCode::OK,
            Json(json!({"success": true, "data": cached, "cached": true})),
        ));
    }
    match bonus_utils::user_points_summary(&s, user.id).await {
        Ok(summary) => {
            cache_set(&key, &summary, 300);
            Ok((
                StatusCode::OK,
                Json(json!({"success": true, "data": summary, "cached": false})),
            ))
        }
        Err(e) => {
            tracing::error!("Error getting points summary for {}: {e}", user.email);
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": "Failed to retrieve points summary"})),
            ))
        }
    }
}

#[utoipa::path(
    get,
    path = "/bonus/history/",
    tag = "Bonus & Rewards",
    summary = "Get bonus transaction history",
    description = "Retrieve user's bonus points transaction history with pagination.",
    params(
        ("type" = Option<String>, Query, description = "Filter by transaction type"),
        ("page" = Option<i64>, Query, description = "Page number"),
        ("page_size" = Option<i64>, Query, description = "Items per page (default 20)"),
    ),
    responses((status = 200, description = "History page"), (status = 500, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn history(
    State(s): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    // int() conversions raise into the 500 branch, like Django.
    let parse = || -> Result<(i64, i64), ()> {
        let page = match params.get("page") {
            Some(v) => v.parse::<i64>().map_err(|_| ())?,
            None => 1,
        };
        let size = match params.get("page_size") {
            Some(v) => v.parse::<i64>().map_err(|_| ())?,
            None => 20,
        };
        Ok((page, size))
    };
    let Ok((page, page_size)) = parse() else {
        tracing::error!("Error getting history for {}", user.email);
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"success": false, "error": "Failed to retrieve history"})),
        ));
    };

    let result: Result<Value, AppError> = async {
        let filter = params.get("type").cloned().unwrap_or_default();
        let mut sql = "SELECT id, transaction_type, CAST(points AS TEXT), reason, description, reference,
                       CAST(balance_before AS TEXT), CAST(balance_after AS TEXT), CAST(created_at AS TEXT), metadata
                FROM bonus_bonushistory WHERE user_id = ?".to_string();
        if !filter.is_empty() {
            sql.push_str(" AND transaction_type = ?");
        }
        sql.push_str(" ORDER BY created_at DESC");
        let mut q = sqlx::query_as::<_, (
            i64, String, String, Option<String>, String, Option<String>, String, String, String,
            Option<String>,
        )>(&sql);
        q = q.bind(user.id);
        if !filter.is_empty() {
            q = q.bind(&filter);
        }
        let rows = q.fetch_all(&s.db).await?;
        let total = rows.len() as i64;
        // Python slice semantics, like Django's list slicing.
        let start = (page - 1) * page_size;
        let items: Vec<Value> = if page_size <= 0 {
            vec![]
        } else {
            let len = rows.len() as i64;
            let from = start.max(0).min(len) as usize;
            let to = (start + page_size).max(0).min(len) as usize;
            let (from, to) = if start < 0 {
                // Negative start counts from the end, like Python.
                let f = (len + start).max(0) as usize;
                let t = (len + start + page_size).max(0).min(len) as usize;
                (f.min(t), t)
            } else {
                (from.min(to), to)
            };
            let mut out = Vec::new();
            for (id, tt, pts, reason, desc, reference, before, after, created, meta) in
                &rows[from..to]
            {
                out.push(json!({
                    "id": id,
                    "transaction_type": tt,
                    "transaction_type_display": super::serializers::type_label_pub(tt),
                    "points": crate::wallet::models::dec2(pts),
                    "reason": reason,
                    "reason_display": super::serializers::reason_label_pub(reason.as_deref()),
                    "description": desc,
                    "reference": reference,
                    "balance_before": crate::wallet::models::dec2(before),
                    "balance_after": crate::wallet::models::dec2(after),
                    "created_at": crate::transactions::serializers::format_created_at_lagos(created),
                    "metadata": meta.as_deref().and_then(|m| serde_json::from_str::<Value>(m).ok()),
                }));
            }
            out
        };
        Ok(json!({
            "success": true,
            "count": total,
            "page": page,
            "page_size": page_size,
            "data": items,
        }))
    }
    .await;
    match result {
        Ok(v) => Ok((StatusCode::OK, Json(v))),
        Err(e) => {
            tracing::error!("Error getting history: {e:?}");
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": "Failed to retrieve history"})),
            ))
        }
    }
}

#[utoipa::path(
    get,
    path = "/bonus/daily-login/",
    tag = "Bonus & Rewards",
    summary = "Claim daily login bonus",
    description = "Claim daily login bonus points (once per day).",
    responses(
        (status = 200, description = "Bonus claimed"),
        (status = 400, description = "Already claimed today"),
        (status = 500, description = "Failed"),
    ),
    security(("bearer" = [])),
)]
pub async fn daily_login(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    match bonus_utils::award_daily_login_bonus(&s, user.id).await {
        Ok(Some((earned, total))) => Ok((
            StatusCode::OK,
            Json(json!({
                "success": true,
                "message": "Daily login bonus claimed!",
                "data": {
                    "points_earned": earned.to_string(),
                    "new_balance": total.to_string(),
                },
            })),
        )),
        Ok(None) => Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "success": false,
                "message": "You have already claimed your daily bonus today",
            })),
        )),
        Err(e) => {
            tracing::error!("Error claiming daily bonus for {}: {e}", user.email);
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": "Failed to claim daily bonus"})),
            ))
        }
    }
}

#[utoipa::path(
    get,
    path = "/bonus/campaigns/",
    tag = "Bonus & Rewards",
    summary = "Get active campaigns",
    description = "Retrieve all currently active bonus campaigns.",
    responses((status = 200, description = "Campaign list"), (status = 500, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn campaigns(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    // 15-minute page cache, like Django's cache_page.
    if let Some(cached) = cache_get("bonus_campaigns") {
        return Ok((StatusCode::OK, Json(cached)));
    }
    let now = crate::time::now_str();
    match bonus_models::running_campaigns(&s.db, &now).await {
        Ok(rows) => {
            let data: Vec<Value> = rows
                .iter()
                .map(|c| {
                    serde_json::to_value(&BonusCampaignPublic::from_row(c))
                        .unwrap_or(Value::Null)
                })
                .collect();
            let body = json!({"success": true, "count": rows.len(), "data": data});
            cache_set("bonus_campaigns", &body, 900);
            Ok((StatusCode::OK, Json(body)))
        }
        Err(e) => {
            tracing::error!("Error getting campaigns: {e}");
            Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": "Failed to retrieve campaigns"})),
            ))
        }
    }
}

#[utoipa::path(
    get,
    path = "/bonus/referral/",
    tag = "Bonus & Rewards",
    summary = "Get my referrals",
    description = "List users referred by the authenticated user with counts.",
    responses((status = 200, description = "Referral list"), (status = 500, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn referral_list(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let rows = bonus_models::referrals_made(&s.db, user.id).await?;
    let mut data = Vec::new();
    for r in &rows {
        let created: Option<(String,)> = sqlx::query_as(
            "SELECT CAST(created_at AS TEXT) FROM bonus_referral WHERE id = ?",
        )
        .bind(r.id)
        .fetch_optional(&s.db)
        .await?;
        let completed: Option<(Option<String>,)> = sqlx::query_as(
            "SELECT CAST(completed_at AS TEXT) FROM bonus_referral WHERE id = ?",
        )
        .bind(r.id)
        .fetch_optional(&s.db)
        .await?;
        data.push(
            ReferralPublic::from_row(
                &s.db,
                r,
                &created.map(|(c,)| c).unwrap_or_default(),
                completed.and_then(|(c,)| c).as_deref(),
            )
            .await,
        );
    }
    let total = rows.len() as i64;
    let completed = rows.iter().filter(|r| r.status == "completed").count() as i64;
    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "data": data.iter().map(|d| serde_json::to_value(d).unwrap_or(Value::Null)).collect::<Vec<_>>(),
            "referral_count": total,
            "completed_count": completed,
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/bonus/referral/",
    tag = "Bonus & Rewards",
    summary = "Apply a referral code",
    description = "Apply a referral code to earn signup bonus points and record the referral.",
    request_body = crate::bonus::serializers::ReferralApplyBody,
    responses(
        (status = 201, description = "Referral applied"),
        (status = 400, description = "Invalid or duplicate code"),
        (status = 500, description = "Failed"),
    ),
    security(("bearer" = [])),
)]
pub async fn referral_apply(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let code = body
        .get("referral_code")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    if code.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": "Referral code is required"})),
        ));
    }
    let referrer: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM accounts_profile WHERE referral_code = ?",
    )
    .bind(&code)
    .fetch_optional(&s.db)
    .await?;
    let Some((referrer_id,)) = referrer else {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": "Invalid referral code"})),
        ));
    };
    if code == user.referral_code {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": "You cannot refer yourself"})),
        ));
    }
    if bonus_models::referral_for_referred(&s.db, user.id)
        .await?
        .is_some()
    {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"success": false, "error": "You have already used a referral code"})),
        ));
    }

    let now = crate::time::now_str();
    let referral_id = match bonus_models::insert_referral(&s.db, referrer_id, user.id, &code, &now)
        .await
    {
        Ok(id) => id,
        Err(e) => {
            tracing::error!("Error adding referral for {}: {e}", user.email);
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": "Failed to add referral"})),
            ));
        }
    };
    let awarded = bonus_utils::award_signup_bonus(&s, user.id).await;
    let row = sqlx::query_as::<_, bonus_models::ReferralRow>(
        "SELECT id, status, bonus_awarded, first_transaction_completed, created_at, completed_at,
                referred_user_id, referrer_id, count, referral_code
         FROM bonus_referral WHERE id = ?",
    )
    .bind(referral_id)
    .fetch_one(&s.db)
    .await?;
    let created: (String,) = sqlx::query_as(
        "SELECT CAST(created_at AS TEXT) FROM bonus_referral WHERE id = ?",
    )
    .bind(referral_id)
    .fetch_one(&s.db)
    .await?;
    let public = ReferralPublic::from_row(&s.db, &row, &created.0, None).await;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "success": true,
            "message": if awarded {
                "Referral applied successfully. You received 20 bonus points!"
            } else {
                "Referral applied successfully."
            },
            "data": serde_json::to_value(&public).unwrap_or(Value::Null),
            "signup_bonus_awarded": awarded,
        })),
    ))
}
