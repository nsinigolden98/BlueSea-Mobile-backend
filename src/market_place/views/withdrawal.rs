//! Withdrawal endpoints. Mirrors `VerifyAccountNameView` and
//! `EventWithdrawalView` (POST withdraw + GET history) in
//! `market_place/views.py`.
//!
//! Note the faithful quirk: the 90% credit / 5%-labeled fee in the code
//! (`platform_fee = available * 0.05`) while copy says 10% — kept as-is.

use axum::{
    Json,
    extract::{Query, Request, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};
use std::collections::HashMap;

use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::{Resp, forbidden, me, not_found, parse_body, path_hex};
use crate::market_place::models as m;
use crate::market_place::serializers as s;

#[utoipa::path(
    post,
    path = "/marketplace/verify-account-name/",
    tag = "Marketplace Withdrawal",
    summary = "Verify bank account name",
    responses((status = 200, description = "Resolved"), (status = 404, description = "Could not resolve")),
    security(("bearer" = [])),
)]
pub async fn verify_account_name(
    State(st): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Resp, AppError> {
    let _user = me(&st, headers).await?;
    let form = parse_body(req, 1024 * 1024).await?;
    let account_number = form.fields.get("account_number").map(|v| v.trim().to_string()).unwrap_or_default();
    let bank_code = form.fields.get("bank_code").map(|v| v.trim().to_string()).unwrap_or_default();
    if account_number.is_empty() || bank_code.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "Account number and bank code are required"}))));
    }
    let result: Value =
        crate::transactions::nomba_gateway::lookup_account_name(&st.config, &account_number, &bank_code)
            .await;
    if result.get("success").and_then(|v| v.as_bool()) == Some(true) {
        Ok((StatusCode::OK, Json(result)))
    } else {
        Ok((StatusCode::NOT_FOUND, Json(result)))
    }
}

struct Earnings {
    total_cents: i64,
    created_count: i64,
    available_count: i64,
}

async fn earnings(db: &sqlx::PgPool, event: &m::EventInfo) -> Result<Earnings, sqlx::Error> {
    if event.is_free {
        return Ok(Earnings { total_cents: 0, created_count: 0, available_count: 0 });
    }
    let rows: Vec<(String, i64, i64)> = sqlx::query_as(
        "SELECT CAST(price AS TEXT), quantity_available, initial_quantity FROM market_place_tickettype WHERE event_id = CAST($1 AS UUID)",
    )
    .bind(&event.id)
    .fetch_all(db)
    .await?;
    let mut total = 0i64;
    let mut created = 0i64;
    let mut available = 0i64;
    for (price, qty_avail, initial) in rows {
        let cents = crate::wallet::models::parse_cents(&price).unwrap_or(0);
        total += cents * (initial - qty_avail);
        created += initial;
        available += qty_avail;
    }
    Ok(Earnings { total_cents: total, created_count: created, available_count: available })
}

async fn total_withdrawn(db: &sqlx::PgPool, event_hex: &str) -> i64 {
    let rows: Vec<(String,)> = sqlx::query_as(
        "SELECT CAST(amount AS TEXT) FROM market_place_eventwithdrawal WHERE event_id = CAST($1 AS UUID) AND status = 'successful'",
    )
    .bind(event_hex)
    .fetch_all(db)
    .await
    .unwrap_or_default();
    rows.iter().filter_map(|r| crate::wallet::models::parse_cents(&r.0).ok()).sum()
}

#[utoipa::path(
    post,
    path = "/marketplace/withdraw/",
    tag = "Marketplace Withdrawal",
    summary = "Withdraw event earnings",
    description = "Withdraw available earnings to the vendor wallet. 90% credited, fee deducted.",
    responses((status = 201, description = "Withdrawn"), (status = 400, description = "Nothing available"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn withdraw(
    State(st): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let form = parse_body(req, 1024 * 1024).await?;
    let event_raw = form.fields.get("event_id").map(|v| v.trim().to_string()).unwrap_or_default();
    if event_raw.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "Event ID is required"}))));
    }
    let hex = path_hex(&event_raw).map_err(|_| AppError::not_found("Event not found"))?;
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };
    let vendor = m::vendor_for_user(&st.db, user.id).await?;
    match vendor {
        Some(v) if v.id == event.vendor_id => {}
        Some(_) => {
            return Ok(forbidden("You can only withdraw from your own events"));
        }
        None => {
            return Ok(forbidden("Only vendors can withdraw"));
        }
    }

    let earn = earnings(&st.db, &event).await?;
    let withdrawn_cents = total_withdrawn(&st.db, &hex).await;
    let available_cents = earn.total_cents - withdrawn_cents;
    if available_cents <= 0 {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "No funds available for withdrawal"}))));
    }
    // Django: fee = 5% of available, credit = 95% — while copy says 90/10.
    let fee_cents = available_cents * 5 / 100;
    let credit_cents = available_cents - fee_cents;
    let payment_ref = format!("BS-MARK-{}", uuid::Uuid::new_v4().simple().to_string()[..12].to_uppercase());
    let wallet = match crate::wallet::models::get_by_user(&st.db, user.id).await? {
        Some(w) => w,
        None => {
            return Ok(not_found("Wallet not found. Please contact support."));
        }
    };
    if let Err(e) = crate::wallet::models::credit(
        &st.db,
        &st.wallet_hub,
        wallet.id,
        user.id,
        &crate::wallet::models::cents_to_decimal(credit_cents),
        &format!(
            "Event withdrawal: {} (90% of ₦{}, 10% platform fee)",
            event.event_title,
            crate::wallet::models::cents_to_decimal(available_cents)
        ),
        Some(&payment_ref),
    )
    .await
    {
        tracing::error!("event withdrawal credit failed: {e:?}");
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": format!("Failed to process withdrawal: {e:?}")})),
        ));
    }

    let now = now_str();
    let withdrawal_id = m::new_id();
    sqlx::query(
        "INSERT INTO market_place_eventwithdrawal
         (id, amount, status, payment_reference, created_at, completed_at, event_id, amount_credited, platform_fee)
         VALUES (CAST($1 AS UUID), CAST($2 AS NUMERIC), 'successful', $3, $4, $5, CAST($6 AS UUID), CAST($7 AS NUMERIC), CAST($8 AS NUMERIC))",
    )
    .bind(&withdrawal_id)
    .bind(crate::wallet::models::cents_to_decimal(available_cents))
    .bind(&payment_ref)
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(&hex)
    .bind(crate::wallet::models::cents_to_decimal(credit_cents))
    .bind(crate::wallet::models::cents_to_decimal(fee_cents))
    .execute(&st.db)
    .await?;
    let row: m::EventWithdrawal = sqlx::query_as(&format!("SELECT {} FROM market_place_eventwithdrawal WHERE id = CAST($1 AS UUID)", m::WITHDRAWAL_COLS))
        .bind(&withdrawal_id)
        .fetch_one(&st.db)
        .await?;
    let public = s::withdrawal_public(&st.db, &row).await;
    let new_withdrawn = withdrawn_cents + available_cents;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "state": true,
            "message": format!("Withdrawal successful! ₦{} added to your wallet (10% platform fee deducted)", crate::wallet::models::cents_to_decimal(credit_cents)),
            "event_summary": {
                "total_earned": crate::wallet::models::cents_to_decimal(earn.total_cents),
                "total_withdrawn": crate::wallet::models::cents_to_decimal(new_withdrawn),
                "amount_left": crate::wallet::models::cents_to_decimal(earn.total_cents - new_withdrawn),
                "total_tickets_created": earn.created_count,
                "tickets_available": earn.available_count,
            },
            "withdrawal": public,
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/withdraw/",
    tag = "Marketplace Withdrawal",
    summary = "Get event withdrawal history",
    params(("event_id" = String, Query, description = "Event UUID")),
    responses((status = 200, description = "History with totals"), (status = 400, description = "Missing event_id"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn withdrawal_history(
    State(st): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let event_raw = params.get("event_id").map(|v| v.trim().to_string()).unwrap_or_default();
    if event_raw.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "event_id is required"}))));
    }
    let hex = path_hex(&event_raw).map_err(|_| AppError::not_found("Event not found"))?;
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };
    let vendor = m::vendor_for_user(&st.db, user.id).await?;
    match vendor {
        Some(v) if v.id == event.vendor_id => {}
        Some(_) => {
            return Ok(forbidden("You can only view your own event withdrawals"));
        }
        None => {
            return Ok(forbidden("Only vendors can view withdrawals"));
        }
    }
    let earn = earnings(&st.db, &event).await?;
    let withdrawn_cents = total_withdrawn(&st.db, &hex).await;
    let rows: Vec<m::EventWithdrawal> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_eventwithdrawal WHERE event_id = CAST($1 AS UUID) ORDER BY created_at DESC", m::WITHDRAWAL_COLS),
    )
    .bind(&hex)
    .fetch_all(&st.db)
    .await?;
    let mut out = Vec::new();
    for w in &rows {
        out.push(s::withdrawal_public(&st.db, w).await);
    }
    Ok((
        StatusCode::OK,
        Json(json!({
            "withdrawals": out,
            "summary": {
                "total_earned": crate::wallet::models::cents_to_decimal(earn.total_cents),
                "total_withdrawn": crate::wallet::models::cents_to_decimal(withdrawn_cents),
                "amount_left": crate::wallet::models::cents_to_decimal(earn.total_cents - withdrawn_cents),
                "total_tickets_created": earn.created_count,
                "tickets_available": earn.available_count,
            },
        })),
    ))
}
