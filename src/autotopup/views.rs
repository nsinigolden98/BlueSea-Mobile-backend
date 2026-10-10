//! Auto top-up endpoints. Mirrors `autotopup/views.py`:
//! create (PIN + fund lock), list, detail/PUT/PATCH/DELETE, cancel,
//! reactivate, history.

use axum::{Json, extract::{Path, State}, http::{HeaderMap, StatusCode}};
use rust_decimal::Decimal;
use serde_json::{Value, json};
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::notifications::utils::{NotifyContext, send_notification};
use crate::state::AppState;
use crate::transactions::serializers::format_created_at_lagos;
use crate::wallet::models as wallet_models;

use super::models as topup_models;
use super::serializers as topup_serializers;

type Resp = (StatusCode, Json<Value>);

async fn public_for(
    s: &AppState,
    user_id: i64,
    t: &topup_models::AutoTopUpRow,
) -> Result<Value, AppError> {
    let raws: Option<(String, String, Option<String>, String, String)> = sqlx::query_as(
        "SELECT CAST(start_date AS TEXT), CAST(next_run AS TEXT), CAST(last_run AS TEXT),
                CAST(created_at AS TEXT), CAST(updated_at AS TEXT)
         FROM autotopup_autotopup WHERE id = $1",
    )
    .bind(t.id)
    .fetch_optional(&s.db)
    .await?;
    let (start_raw, next_raw, last_raw, created_raw, updated_raw) =
        raws.unwrap_or_default();
    let wallet: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(&s.db)
    .await?;
    let public = topup_serializers::public_from_row(
        t,
        &start_raw,
        &next_raw,
        last_raw.as_deref(),
        &created_raw,
        &updated_raw,
        &wallet.map(|(b,)| b).unwrap_or_else(|| "0".to_string()),
    );
    Ok(serde_json::to_value(&public).unwrap_or(Value::Null))
}

#[utoipa::path(
    post,
    path = "/autotopup/create/",
    tag = "Auto Top-Up",
    summary = "Create a new auto top-up",
    description = "Schedule a new auto top-up. Funds will be locked from wallet. Requires transaction PIN.",
    request_body = crate::autotopup::serializers::AutoTopUpCreateBody,
    responses(
        (status = 201, description = "Top-up created"),
        (status = 400, description = "Validation or funds failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn create(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = match crate::payments::views::common::pin_gate(&s, headers, &body, false).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    // PIN is stripped before validation, like Django's data.pop().
    let mut payload = body.clone();
    if let Value::Object(map) = &mut payload {
        map.remove("transaction_pin");
    }
    let input = match topup_serializers::validate_full(&payload) {
        Ok(i) => i,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };

    // Create-time balance gate (AutoTopUpCreateSerializer).
    let wallet: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user.id)
    .fetch_optional(&s.db)
    .await?;
    let available = wallet.map(|(b,)| b).unwrap_or_else(|| "0".to_string());
    let balance_dec: Decimal = available.parse().unwrap_or(Decimal::ZERO);
    let amount = input.amount.unwrap_or(Decimal::ZERO);
    if balance_dec < amount {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"amount": format!("Insufficient funds. Available balance: ₦{available}")})),
        ));
    }

    let now = crate::time::now_str();
    let start_storage = input
        .start_date
        .map(|d| d.format("%Y-%m-%d %H:%M:%S%.f").to_string())
        .unwrap_or_else(|| now.clone());
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO autotopup_autotopup (service_type, amount, phone_number, network, plan, start_date,
                repeat_days, is_active, next_run, is_locked, locked_amount, last_run, total_runs, failed_runs,
                created_at, updated_at, user_id)
         VALUES ($1, CAST($2 AS NUMERIC), $3, $4, $5, $6, $7, $8, $9, FALSE, '0.00', NULL, 0, 0, $10, $11, $12) RETURNING id",
    )
    .bind(input.service_type.clone().unwrap_or_default())
    .bind(amount.to_string())
    .bind(input.phone_number.clone().unwrap_or_default())
    .bind(input.network.clone())
    .bind(input.plan.clone())
    .bind(crate::time::Ts(&start_storage))
    .bind(input.repeat_days.unwrap_or(0))
    .bind(input.is_active.unwrap_or(true))
    .bind(crate::time::Ts(&start_storage))
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(user.id)
    .fetch_one(&s.db)
    .await?;
    let id = res.0;

    if !topup_models::lock_funds(&s.db, user.id, id, amount, &now).await? {
        let _ = sqlx::query("DELETE FROM autotopup_autotopup WHERE id = $1")
            .bind(id)
            .execute(&s.db)
            .await;
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Failed to lock funds. Please try again."})),
        ));
    }

    let row = topup_models::get_for_user(&s.db, id, user.id)
        .await?
        .ok_or_else(|| AppError::internal("top-up vanished"))?;
    let service_label = if row.service_type == "airtime" { "Airtime" } else { "Data" };
    let frequency = if row.repeat_days == 0 {
        "one-time".to_string()
    } else {
        format!("every {} days", row.repeat_days)
    };
    let mut ctx = NotifyContext::default();
    ctx.service_type = service_label.to_string();
    ctx.amount = amount.to_string();
    ctx.phone_number = row.phone_number.clone();
    ctx.network = row.network.clone().unwrap_or_else(|| "N/A".to_string());
    ctx.start_date = start_storage.clone();
    ctx.frequency = frequency.clone();
    ctx.locked_amount = amount.to_string();
    let _ = send_notification(
        &s, user.id, &user.email, &user.other_names,
        "Auto Top-Up Created",
        &format!(
            "{service_label} auto top-up of ₦{amount} scheduled {frequency}. ₦{amount} has been locked from your wallet."
        ),
        "success",
        Some("BlueSea Mobile - Auto Top-Up Scheduled"),
        ctx,
    )
    .await
    .map_err(|e| tracing::warn!("notification failed: {e}"));

    Ok((StatusCode::CREATED, Json(public_for(&s, user.id, &row).await?)))
}

#[utoipa::path(
    get,
    path = "/autotopup/list/",
    tag = "Auto Top-Up",
    summary = "List user's auto top-ups",
    description = "Retrieve all auto top-up schedules for the authenticated user.",
    responses((status = 200, description = "Top-up list")),
    security(("bearer" = [])),
)]
pub async fn list(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let rows = topup_models::list_for_user(&s.db, user.id).await?;
    let mut out = Vec::new();
    for t in &rows {
        out.push(public_for(&s, user.id, t).await?);
    }
    Ok((StatusCode::OK, Json(Value::Array(out))))
}

async fn detail_public(
    s: &AppState,
    user_id: i64,
    t: &topup_models::AutoTopUpRow,
) -> Result<Value, AppError> {
    let mut v = public_for(s, user_id, t).await?;
    let history = topup_models::history_for(&s.db, t.id, user_id).await?;
    let mut items = Vec::new();
    for h in &history {
        let raw: Option<(String,)> = sqlx::query_as(
            "SELECT CAST(executed_at AS TEXT) FROM autotopup_autotopuphistory WHERE id = $1",
        )
        .bind(h.id)
        .fetch_optional(&s.db)
        .await?;
        items.push(json!({
            "id": h.id,
            "service_type": t.service_type,
            "phone_number": t.phone_number,
            "amount": crate::wallet::models::dec2(&h.amount),
            "status": h.status,
            "vtu_reference": h.vtu_reference,
            "error_message": h.error_message,
            "executed_at": format_created_at_lagos(&raw.map(|(r,)| r).unwrap_or_default()),
        }));
    }
    if let Value::Object(map) = &mut v {
        map.insert("history".to_string(), Value::Array(items));
    }
    Ok(v)
}

#[utoipa::path(
    get,
    path = "/autotopup/{pk}/",
    tag = "Auto Top-Up",
    summary = "Get auto top-up details",
    description = "Retrieve detailed information about a specific auto top-up including history.",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses((status = 200, description = "Detail"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn detail(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    match topup_models::get_for_user(&s.db, pk, user.id).await? {
        Some(t) => Ok((StatusCode::OK, Json(detail_public(&s, user.id, &t).await?))),
        None => Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Auto top-up not found"})),
        )),
    }
}

async fn apply_update(
    s: &AppState,
    user_id: i64,
    id: i64,
    input: &topup_serializers::TopUpInput,
    now: &str,
) -> Result<(), AppError> {
    // Writable fields only; read-only keys (next_run, locks, counters,
    // timestamps) are ignored, like DRF read_only_fields.
    let mut sets: Vec<String> = Vec::new();
    let mut binds: Vec<String> = Vec::new();
    if let Some(v) = input.service_type.as_deref() {
        sets.push("service_type = ?".to_string());
        binds.push(v.to_string());
    }
    if let Some(v) = input.amount.as_ref() {
        sets.push("amount = ?".to_string());
        binds.push(v.to_string());
    }
    if let Some(v) = input.phone_number.as_deref() {
        sets.push("phone_number = ?".to_string());
        binds.push(v.to_string());
    }
    if input.network.is_some() {
        sets.push("network = ?".to_string());
        binds.push(input.network.clone().unwrap_or_default());
    }
    if input.plan.is_some() {
        sets.push("plan = ?".to_string());
        binds.push(input.plan.clone().unwrap_or_default());
    }
    if let Some(v) = input.start_date {
        sets.push("start_date = ?".to_string());
        binds.push(v.format("%Y-%m-%d %H:%M:%S%.f").to_string());
    }
    if let Some(v) = input.repeat_days {
        sets.push("repeat_days = ?".to_string());
        binds.push(v.to_string());
    }
    if let Some(v) = input.is_active {
        sets.push("is_active = ?".to_string());
        binds.push(if v { "1".to_string() } else { "0".to_string() });
    }
    if sets.is_empty() {
        return Ok(());
    }
    sets.push("updated_at = ?".to_string());
    let sql = format!(
        "UPDATE autotopup_autotopup SET {} WHERE id = $1 AND user_id = $2",
        sets.join(", ")
    );
    let mut q = sqlx::query(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    q.bind(crate::time::Ts(&now)).bind(id).bind(user_id).execute(&s.db).await?;
    Ok(())
}

#[utoipa::path(
    put,
    path = "/autotopup/{pk}/",
    tag = "Auto Top-Up",
    summary = "Update auto top-up",
    description = "Update an existing auto top-up schedule (full update).",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses((status = 200, description = "Updated"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn update_full(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    update_inner(&s, headers, pk, &body, true).await
}

#[utoipa::path(
    patch,
    path = "/autotopup/{pk}/",
    tag = "Auto Top-Up",
    summary = "Partially update auto top-up",
    description = "Partially update an existing auto top-up schedule.",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses((status = 200, description = "Updated"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn update_partial(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    update_inner(&s, headers, pk, &body, false).await
}

async fn update_inner(
    s: &AppState,
    headers: HeaderMap,
    pk: i64,
    body: &Value,
    full: bool,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    if topup_models::get_for_user(&s.db, pk, user.id).await?.is_none() {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Auto top-up not found"})),
        ));
    }
    let input = if full {
        match topup_serializers::validate_full(body) {
            Ok(i) => i,
            Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
        }
    } else {
        match topup_serializers::validate_partial(body) {
            Ok(i) => i,
            Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
        }
    };
    let now = crate::time::now_str();
    apply_update(s, user.id, pk, &input, &now).await?;
    let _ = send_notification(
        s, user.id, &user.email, &user.other_names,
        "Auto Top-Up Updated",
        &format!(
            "Your {} auto top-up schedule has been updated.",
            input.service_type.as_deref().unwrap_or("auto")
        ),
        "info", None, NotifyContext::default(),
    )
    .await
    .map_err(|_| ());
    let row = topup_models::get_for_user(&s.db, pk, user.id)
        .await?
        .ok_or_else(|| AppError::not_found("Auto top-up not found"))?;
    Ok((StatusCode::OK, Json(public_for(s, user.id, &row).await?)))
}

#[utoipa::path(
    delete,
    path = "/autotopup/{pk}/",
    tag = "Auto Top-Up",
    summary = "Delete auto top-up",
    description = "Delete an auto top-up schedule and unlock funds.",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses((status = 204, description = "Deleted"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn delete(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let row = match topup_models::get_for_user(&s.db, pk, user.id).await? {
        Some(t) => t,
        None => {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Auto top-up not found"})),
            ))
        }
    };
    let unlocked = row.locked_amount.clone();
    let service_type = row.service_type.clone();
    let now = crate::time::now_str();
    let _ = topup_models::unlock_funds(&s.db, user.id, pk, &now).await;
    // Django cascades history rows on delete.
    let _ = sqlx::query("DELETE FROM autotopup_autotopuphistory WHERE auto_topup_id = $1")
        .bind(pk)
        .execute(&s.db)
        .await;
    let _ = sqlx::query("DELETE FROM autotopup_autotopup WHERE id = $1 AND user_id = $2")
        .bind(pk)
        .bind(user.id)
        .execute(&s.db)
        .await;
    let mut ctx = NotifyContext::default();
    ctx.unlocked_amount = unlocked.clone();
    ctx.service_type = service_type.clone();
    let _ = send_notification(
        &s, user.id, &user.email, &user.other_names,
        "Auto Top-Up Deleted",
        &format!(
            "Your {service_type} auto top-up has been deleted. ₦{unlocked} has been returned to your wallet."
        ),
        "info", None, ctx,
    )
    .await
    .map_err(|_| ());
    Ok((StatusCode::NO_CONTENT, Json(Value::Null)))
}

#[utoipa::path(
    patch,
    path = "/autotopup/{pk}/cancel/",
    tag = "Auto Top-Up",
    summary = "Cancel auto top-up",
    description = "Cancel an auto top-up schedule and unlock the reserved funds.",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses(
        (status = 200, description = "Cancelled"),
        (status = 400, description = "Already inactive or unlock failed"),
        (status = 404, description = "Not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn cancel(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let row = match topup_models::get_for_user(&s.db, pk, user.id).await? {
        Some(t) => t,
        None => {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Auto top-up not found"})),
            ))
        }
    };
    if !row.is_active {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Auto top-up is already inactive"})),
        ));
    }
    let unlocked = row.locked_amount.clone();
    let service_type = row.service_type.clone();
    let now = crate::time::now_str();
    let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = FALSE, updated_at = $1 WHERE id = $2")
        .bind(crate::time::Ts(&now))
        .bind(pk)
        .execute(&s.db)
        .await;
    if topup_models::unlock_funds(&s.db, user.id, pk, &now).await? {
        let mut ctx = NotifyContext::default();
        ctx.service_type = service_type.clone();
        ctx.unlocked_amount = unlocked.clone();
        let _ = send_notification(
            &s, user.id, &user.email, &user.other_names,
            "Auto Top-Up Cancelled",
            &format!(
                "Your {service_type} auto top-up has been cancelled. ₦{unlocked} has been returned to your wallet."
            ),
            "warning",
            Some("BlueSea Mobile - Auto Top-Up Cancelled"),
            ctx,
        )
        .await
        .map_err(|_| ());
        return Ok((
            StatusCode::OK,
            Json(json!({
                "message": "Auto top-up cancelled successfully",
                "unlocked_amount": unlocked,
            })),
        ));
    }
    Ok((
        StatusCode::BAD_REQUEST,
        Json(json!({"error": "Failed to unlock funds"})),
    ))
}

#[utoipa::path(
    patch,
    path = "/autotopup/{pk}/reactivate/",
    tag = "Auto Top-Up",
    summary = "Reactivate auto top-up",
    description = "Reactivate a cancelled auto top-up. Funds will be locked again. Requires transaction PIN.",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses(
        (status = 200, description = "Reactivated"),
        (status = 400, description = "Already active, insufficient funds or lock failed"),
        (status = 404, description = "Not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn reactivate(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = match crate::payments::views::common::pin_gate(&s, headers, &body, false).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let row = match topup_models::get_for_user(&s.db, pk, user.id).await? {
        Some(t) => t,
        None => {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Auto top-up not found"})),
            ))
        }
    };
    if row.is_active {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Auto top-up is already active"})),
        ));
    }
    let wallet: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user.id)
    .fetch_optional(&s.db)
    .await?;
    let balance = wallet
        .as_ref()
        .and_then(|(b,)| wallet_models::parse_cents(b).ok())
        .unwrap_or(0);
    let amount = wallet_models::parse_cents(&row.amount).unwrap_or(i64::MAX);
    if balance < amount {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Insufficient funds"})),
        ));
    }
    let now = crate::time::now_str();
    let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = TRUE, updated_at = $1 WHERE id = $2")
        .bind(crate::time::Ts(&now))
        .bind(pk)
        .execute(&s.db)
        .await;
    let amount_dec: Decimal = row.amount.parse().unwrap_or(Decimal::ZERO);
    if topup_models::lock_funds(&s.db, user.id, pk, amount_dec, &now).await? {
        let locked = row.amount.clone();
        let mut ctx = NotifyContext::default();
        ctx.service_type = row.service_type.clone();
        ctx.locked_amount = locked.clone();
        let next_raw: Option<(String,)> = sqlx::query_as(
            "SELECT CAST(next_run AS TEXT) FROM autotopup_autotopup WHERE id = $1",
        )
        .bind(pk)
        .fetch_optional(&s.db)
        .await?;
        ctx.next_run = next_raw.map(|(r,)| r).unwrap_or_default();
        let _ = send_notification(
            &s, user.id, &user.email, &user.other_names,
            "Auto Top-Up Reactivated",
            &format!(
                "Your {} auto top-up has been reactivated. ₦{locked} has been locked from your wallet.",
                row.service_type
            ),
            "success",
            Some("BlueSea Mobile - Auto Top-Up Reactivated"),
            ctx,
        )
        .await
        .map_err(|_| ());
        return Ok((
            StatusCode::OK,
            Json(json!({
                "message": "Auto top-up reactivated successfully",
                "locked_amount": locked,
            })),
        ));
    }
    Ok((
        StatusCode::BAD_REQUEST,
        Json(json!({"error": "Failed to lock funds"})),
    ))
}

#[utoipa::path(
    get,
    path = "/autotopup/{pk}/history/",
    tag = "Auto Top-Up",
    summary = "Get auto top-up history",
    description = "Get execution history for a specific auto top-up.",
    params(("pk" = i64, Path, description = "Top-up ID")),
    responses((status = 200, description = "History list"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn history(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(pk): Path<i64>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    if topup_models::get_for_user(&s.db, pk, user.id).await?.is_none() {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Auto top-up not found"})),
        ));
    }
    let rows = topup_models::history_for(&s.db, pk, user.id).await?;
    let mut out = Vec::new();
    for h in &rows {
        let raw: Option<(String,)> = sqlx::query_as(
            "SELECT CAST(executed_at AS TEXT) FROM autotopup_autotopuphistory WHERE id = $1",
        )
        .bind(h.id)
        .fetch_optional(&s.db)
        .await?;
        let topup = topup_models::get_for_user(&s.db, pk, user.id)
            .await?
            .ok_or_else(|| AppError::not_found("Auto top-up not found"))?;
        out.push(json!({
            "id": h.id,
            "service_type": topup.service_type,
            "phone_number": topup.phone_number,
            "amount": crate::wallet::models::dec2(&h.amount),
            "status": h.status,
            "vtu_reference": h.vtu_reference,
            "error_message": h.error_message,
            "executed_at": format_created_at_lagos(&raw.map(|(r,)| r).unwrap_or_default()),
        }));
    }
    Ok((StatusCode::OK, Json(Value::Array(out))))
}
