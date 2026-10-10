//! Loyalty endpoints. Mirrors `loyalty_market/views.py`:
//! reward list (in-stock only) and detail, points redemption, and the
//! user's redemption history.

use axum::{Json, extract::{Path, State}, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::bonus::models as bonus_models;
use crate::error::AppError;
use crate::state::AppState;
use crate::transactions::serializers::format_created_at_lagos;

use super::models as loyalty_models;
use super::serializers::{RedemptionPublic, RewardPublic, dashed_uuid, normalize_uuid};

type Resp = (StatusCode, Json<Value>);

async fn reward_datetimes(
    s: &AppState,
    id_hex: &str,
) -> (String, Option<String>, String) {
    let row: Option<(String, Option<String>, String)> = sqlx::query_as(
        "SELECT CAST(availability_start AS TEXT), CAST(availability_end AS TEXT), CAST(created_at AS TEXT)
         FROM loyalty_market_reward WHERE id = CAST($1 AS UUID)",
    )
    .bind(id_hex)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    row.map(|(a, b, c)| (a, b, c))
        .unwrap_or_default()
}

#[utoipa::path(
    get,
    path = "/loyalty/rewards/",
    tag = "Loyalty Market",
    summary = "List available rewards",
    description = "List rewards with available inventory.",
    responses((status = 200, description = "Reward list")),
    security(("bearer" = [])),
)]
pub async fn reward_list(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let rows = loyalty_models::available_rewards(&s.db).await?;
    let mut out = Vec::new();
    for r in &rows {
        let (start_raw, end_raw, created_raw) = reward_datetimes(&s, &r.id).await;
        out.push(
            serde_json::to_value(&RewardPublic::from_row(
                r,
                &start_raw,
                end_raw.as_deref(),
                &created_raw,
            ))
            .unwrap_or(Value::Null),
        );
    }
    Ok((
        StatusCode::OK,
        Json(json!({"count": out.len(), "rewards": out})),
    ))
}

#[utoipa::path(
    get,
    path = "/loyalty/rewards/{reward_id}/",
    tag = "Loyalty Market",
    summary = "Get reward details",
    description = "Retrieve a single reward by id.",
    params(("reward_id" = String, Path, description = "Reward UUID")),
    responses((status = 200, description = "Reward"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn reward_detail(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(reward_id): Path<String>,
) -> Result<Resp, AppError> {
    let _user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let hex = normalize_uuid(&reward_id);
    match loyalty_models::reward_by_id(&s.db, &hex).await? {
        Some(r) => {
            let (start_raw, end_raw, created_raw) = reward_datetimes(&s, &r.id).await;
            Ok((
                StatusCode::OK,
                Json(
                    serde_json::to_value(&RewardPublic::from_row(
                        &r,
                        &start_raw,
                        end_raw.as_deref(),
                        &created_raw,
                    ))
                    .unwrap_or(Value::Null),
                ),
            ))
        }
        None => Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"detail": "Not found."})),
        )),
    }
}

#[utoipa::path(
    post,
    path = "/loyalty/rewards/{reward_id}/redeem/",
    tag = "Loyalty Market",
    summary = "Redeem a reward",
    description = "Redeem a reward using bonus points.",
    params(("reward_id" = String, Path, description = "Reward UUID")),
    responses(
        (status = 200, description = "Redeemed"),
        (status = 400, description = "Out of stock or insufficient points"),
        (status = 404, description = "Not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn redeem(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(reward_id): Path<String>,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let hex = normalize_uuid(&reward_id);
    let reward = match loyalty_models::reward_by_id(&s.db, &hex).await? {
        Some(r) => r,
        None => {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"detail": "Not found."})),
            ))
        }
    };

    // Only strictly-negative inventory blocks, like Django
    // (`if reward.inventory and reward.inventory <= 0`).
    if reward.inventory.map(|i| i < 0).unwrap_or(false) {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "This reward is out of stock"})),
        ));
    }

    let points = match bonus_models::get_point(&s.db, user.id).await? {
        Some(p) => p,
        None => {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"error": "You do not have any bonus points"})),
            ))
        }
    };
    let balance: i32 = points
        .points
        .parse::<rust_decimal::Decimal>()
        .map(|d| (d.trunc()).to_string().parse::<i32>().unwrap_or(0))
        .unwrap_or(0);
    if balance < reward.points_cost {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": format!(
                "Insufficient points. You need {} points but have {}",
                reward.points_cost, points.points
            )})),
        ));
    }

    // deduct_points(): zero/negative costs raise into a 500, like Django.
    if reward.points_cost <= 0 {
        return Err(AppError::internal("Points amount must be positive"));
    }

    // Deduct points and create the redemption atomically-ish (sequential
    // statements; Django wraps the ORM calls in one transaction).
    let new_balance = (balance - reward.points_cost).to_string();
    let now = crate::time::now_str();
    let lifetime = points.lifetime_earned.clone();
    let redeemed_total = (points
        .lifetime_redeemed
        .parse::<rust_decimal::Decimal>()
        .unwrap_or(rust_decimal::Decimal::ZERO)
        + rust_decimal::Decimal::from(reward.points_cost))
    .to_string();
    bonus_models::set_point_balances(
        &s.db,
        points.id,
        &new_balance,
        &lifetime,
        &redeemed_total,
        &now,
    )
    .await?;
    let redemption_id = uuid::Uuid::new_v4().simple().to_string();
    let delivery_info = body
        .get("delivery_info")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let payload = serde_json::json!({
        "fulfilment_type": reward.fulfilment_type,
        "delivery_info": delivery_info,
    })
    .to_string();
    let _ = sqlx::query(
        "INSERT INTO loyalty_market_redemptiontransaction
         (id, points_deducted, status, created_at, redeemed_at, fulfilment_payload, user_id_id, reward_id_id)
         VALUES (CAST($1 AS UUID), $2, 'completed', $3, $4, $5, $6, $7)",
    )
    .bind(&redemption_id)
    .bind(reward.points_cost)
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(&payload)
    .bind(user.id)
    .bind(&reward.id)
    .execute(&s.db)
    .await;
    if reward.inventory.map(|i| i != 0).unwrap_or(false) {
        let _ = sqlx::query(
            "UPDATE loyalty_market_reward SET inventory = inventory - 1 WHERE id = CAST($1 AS UUID)",
        )
        .bind(&reward.id)
        .execute(&s.db)
        .await;
    }

    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "message": "Reward redeemed successfully",
            "redemption": {
                "id": dashed_uuid(&redemption_id),
                "reward": reward.title,
                "points_deducted": reward.points_cost,
                "status": "completed",
                "created_at": format_created_at_lagos(&now),
            },
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/loyalty/redemptions/",
    tag = "Loyalty Market",
    summary = "List my redemptions",
    description = "List reward redemptions by the authenticated user.",
    responses((status = 200, description = "Redemption list")),
    security(("bearer" = [])),
)]
pub async fn redemptions(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let rows = loyalty_models::redemptions_for(&s.db, user.id).await?;
    let mut out = Vec::new();
    for (r, title) in &rows {
        let raw: Option<(String,)> = sqlx::query_as(
            "SELECT CAST(created_at AS TEXT) FROM loyalty_market_redemptiontransaction WHERE id = CAST($1 AS UUID)",
        )
        .bind(&r.id)
        .fetch_optional(&s.db)
        .await?;
        out.push(RedemptionPublic {
            id: dashed_uuid(&r.id),
            reward: title.clone().unwrap_or_else(|| "Unknown".to_string()),
            points_deducted: r.points_deducted,
            status: r.status.clone(),
            created_at: format_created_at_lagos(&raw.map(|(c,)| c).unwrap_or_default()),
        });
    }
    Ok((
        StatusCode::OK,
        Json(json!({"count": out.len(), "redemptions": out})),
    ))
}
