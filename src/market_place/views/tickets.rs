//! Ticket endpoints. Mirrors `MyTicketsView`, `TicketListView`,
//! `MyTicketsListView`, `TicketDetailView`, `TransferTicketView`,
//! `CancelTicketView` in `market_place/views.py`.

use axum::{
    Json,
    extract::{Path, Query, Request, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};
use std::collections::HashMap;

use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::{Resp, bad, forbidden, is_valid_email_pub, me, not_found, parse_body, path_hex, scheme_host, verify_pin, now_ts};
use crate::market_place::models as m;
use crate::market_place::serializers as s;

#[utoipa::path(
    get,
    path = "/marketplace/tickets/my/",
    tag = "Marketplace Tickets",
    summary = "Get my tickets",
    description = "Tickets purchased by or assigned to the authenticated user.",
    responses((status = 200, description = "Ticket list")),
    security(("bearer" = [])),
)]
pub async fn my_tickets(
    State(st): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let tickets: Vec<m::IssuedTicket> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_issuedticket WHERE purchased_by_id = $1 OR owner_email = $2 ORDER BY created_at DESC", m::ISSUED_TICKET_COLS),
    )
    .bind(user.id)
    .bind(&user.email)
    .fetch_all(&st.db)
    .await?;
    let mut out = Vec::new();
    for t in &tickets {
        out.push(s::issued_ticket_out(&st.db, t, &scheme, &host).await);
    }
    // DRF returns the bare list here.
    Ok((StatusCode::OK, Json(Value::Array(out.into_iter().map(|v| serde_json::to_value(v).unwrap_or(Value::Null)).collect()))))
}

#[utoipa::path(
    get,
    path = "/marketplace/tickets/",
    tag = "Marketplace Tickets",
    summary = "Get all tickets owned by current user",
    params(("status" = Option<String>, Query, description = "Filter by status")),
    responses((status = 200, description = "Owned tickets with count")),
    security(("bearer" = [])),
)]
pub async fn ticket_list(
    State(st): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let status_filter = params.get("status").map(|v| v.as_str()).unwrap_or("all");
    let mut sql = format!("SELECT {} FROM market_place_issuedticket WHERE owner_email = $1", m::ISSUED_TICKET_COLS);
    if status_filter != "all" {
        sql.push_str(" AND status = $2");
    }
    sql.push_str(" ORDER BY created_at DESC");
    let mut q = sqlx::query_as::<_, m::IssuedTicket>(&sql).bind(&user.email);
    if status_filter != "all" {
        q = q.bind(status_filter);
    }
    let tickets = q.fetch_all(&st.db).await?;
    let mut out = Vec::new();
    for t in &tickets {
        out.push(s::ticket_list_out(&st.db, t, &scheme, &host).await);
    }
    Ok((
        StatusCode::OK,
        Json(json!({"state": true, "count": out.len(), "tickets": out})),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/mytickets/",
    tag = "Marketplace Tickets",
    summary = "Get my tickets with statistics",
    params(("status" = Option<String>, Query, description = "Filter by status")),
    responses((status = 200, description = "Owned tickets with stats")),
    security(("bearer" = [])),
)]
pub async fn my_tickets_list(
    State(st): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let status_filter = params.get("status").map(|v| v.as_str()).unwrap_or("all");
    let stats: (i64, i64, i64, i64, i64) = sqlx::query_as(
        "SELECT COUNT(*),
                SUM(CASE WHEN status = 'upcoming' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END)
         FROM market_place_issuedticket WHERE owner_email = $1",
    )
    .bind(&user.email)
    .fetch_one(&st.db)
    .await
    .unwrap_or((0, 0, 0, 0, 0));
    let mut sql = format!("SELECT {} FROM market_place_issuedticket WHERE owner_email = $1", m::ISSUED_TICKET_COLS);
    if status_filter != "all" {
        sql.push_str(" AND status = $2");
    }
    sql.push_str(" ORDER BY created_at DESC");
    let mut q = sqlx::query_as::<_, m::IssuedTicket>(&sql).bind(&user.email);
    if status_filter != "all" {
        q = q.bind(status_filter);
    }
    let tickets = q.fetch_all(&st.db).await?;
    let mut out = Vec::new();
    for t in &tickets {
        out.push(s::ticket_list_out(&st.db, t, &scheme, &host).await);
    }
    Ok((
        StatusCode::OK,
        Json(json!({
            "state": true,
            "stats": {"all": stats.0, "upcoming": stats.1, "used": stats.2, "expired": stats.3, "canceled": stats.4},
            "tickets": out,
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/tickets/{ticket_id}/",
    tag = "Marketplace Tickets",
    summary = "Get single ticket details",
    params(("ticket_id" = String, Path, description = "Ticket UUID")),
    responses((status = 200, description = "Ticket detail"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn ticket_detail(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<String>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let hex = path_hex(&ticket_id).map_err(|_| AppError::not_found("Ticket not found"))?;
    let Some(ticket) = m::ticket_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Ticket not found"));
    };
    if ticket.owner_email != user.email {
        return Ok(forbidden("You do not own this ticket"));
    }
    let public = s::ticket_detail_out(&st.db, &st.config.media_root, &ticket, &scheme, &host, now_ts()).await;
    Ok((StatusCode::OK, Json(json!({"state": true, "ticket": public}))))
}

#[utoipa::path(
    post,
    path = "/marketplace/tickets/{ticket_id}/transfer/",
    tag = "Marketplace Tickets",
    summary = "Transfer ticket to another person",
    params(("ticket_id" = String, Path, description = "Ticket UUID")),
    responses((status = 200, description = "Transferred"), (status = 400, description = "Invalid input"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn transfer_ticket(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<String>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let hex = path_hex(&ticket_id).map_err(|_| AppError::not_found("Ticket not found"))?;
    let form = parse_body(req, 1024 * 1024).await?;
    let recipient_email = form.fields.get("recipient_email").map(|v| v.trim().to_string()).unwrap_or_default();
    let recipient_name = form.fields.get("recipient_name").map(|v| v.trim().to_string()).unwrap_or_default();
    if recipient_email.is_empty() || recipient_name.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": "recipient_email and recipient_name are required", "state": false}))));
    }
    if !is_valid_email_pub(&recipient_email) {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"recipient_email": ["Enter a valid email address."]}))));
    }
    if recipient_email.to_lowercase() == user.email.to_lowercase() {
        return Ok(bad("You cannot transfer a ticket to yourself"));
    }
    let Some(ticket) = m::ticket_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Ticket not found"));
    };
    let event = m::event_by_id(&st.db, &ticket.event_id).await?.ok_or_else(|| AppError::internal("Event missing"))?;
    if event.is_canceled {
        return Ok(bad("This event has been canceled"));
    }
    if ticket.owner_email != user.email {
        return Ok(forbidden("You do not own this ticket. Only the current owner can transfer it."));
    }
    let event_date_raw = m::raw_event_date(&st.db, &ticket.event_id).await.ok().flatten().unwrap_or_default();
    let status = s::transfer_status(&ticket.status, ticket.transfer_count, &event_date_raw, now_ts());
    if !status.allowed {
        return Ok(bad(&status.message));
    }
    let previous_owner = ticket.owner_email.clone();
    let now = now_str();
    sqlx::query(
        "UPDATE market_place_issuedticket
         SET owner_name = $1, owner_email = $2, transferred_to = $3, transferred_at = $4,
             transfer_count = transfer_count + 1, status = 'upcoming'
         WHERE id = CAST($5 AS UUID)",
    )
    .bind(&recipient_name)
    .bind(&recipient_email)
    .bind(&recipient_email)
    .bind(crate::time::Ts(&now))
    .bind(&hex)
    .execute(&st.db)
    .await?;
    let transferred_at = crate::transactions::serializers::format_created_at_lagos(&now);
    Ok((
        StatusCode::OK,
        Json(json!({
            "message": format!("Ticket successfully transferred to {recipient_email}. You no longer own this ticket."),
            "state": true,
            "ticket_id": m::dashed(&hex),
            "transferred_to": format!("{recipient_name} ({recipient_email})"),
            "transferred_at": transferred_at,
            "previous_owner": previous_owner,
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/marketplace/tickets/{ticket_id}/cancel/",
    tag = "Marketplace Tickets",
    summary = "Cancel ticket and get refund",
    params(("ticket_id" = String, Path, description = "Ticket UUID")),
    responses((status = 200, description = "Canceled"), (status = 400, description = "Invalid input"), (status = 403, description = "Not the purchaser"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn cancel_ticket(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(ticket_id): Path<String>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let hex = path_hex(&ticket_id).map_err(|_| AppError::not_found("Ticket not found"))?;
    let form = parse_body(req, 1024 * 1024).await?;
    let reason = form.fields.get("reason").map(|v| v.trim().to_string()).unwrap_or_default();
    if reason.is_empty() {
        return Ok(bad("Cancellation reason is required"));
    }
    let Some(ticket) = m::ticket_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Ticket not found"));
    };
    if ticket.purchased_by_id != Some(user.id) {
        return Ok(forbidden("You do not have permission to cancel this ticket"));
    }
    let event = m::event_by_id(&st.db, &ticket.event_id).await?.ok_or_else(|| AppError::internal("Event missing"))?;
    let price_cents = match &ticket.ticket_type_id {
        Some(tt_id) => {
            let row: Option<(String,)> = sqlx::query_as("SELECT CAST(price AS TEXT) FROM market_place_tickettype WHERE id = CAST($1 AS UUID)")
                .bind(tt_id)
                .fetch_optional(&st.db)
                .await?;
            row.and_then(|r| crate::wallet::models::parse_cents(&r.0).ok()).unwrap_or(0)
        }
        None => 0,
    };
    let event_date_raw = m::raw_event_date(&st.db, &ticket.event_id).await.ok().flatten().unwrap_or_default();
    let (allowed, refund_cents, policy) = s::cancel_status(
        &ticket.status,
        ticket.ticket_type_id.is_some(),
        event.is_free,
        price_cents,
        &event_date_raw,
        now_ts(),
    );
    if !allowed {
        return Ok(bad(&policy));
    }
    // Paid tickets require the transaction PIN.
    if ticket.ticket_type_id.is_some() && !event.is_free {
        let pin = form.fields.get("transaction_pin").map(|v| v.as_str()).unwrap_or("");
        if pin.is_empty() {
            return Ok(bad("Transaction PIN is required for paid ticket cancellations"));
        }
        if crate::wallet::models::get_by_user(&st.db, user.id).await?.is_none() {
            return Ok(not_found("Wallet not found"));
        }
        if let Err(e) = verify_pin(&st, user.id, pin).await {
            return Ok(e);
        }
    }

    let now = now_str();
    let refund_store = crate::wallet::models::cents_to_decimal(refund_cents);
    sqlx::query(
        "UPDATE market_place_issuedticket
         SET status = 'canceled', canceled_at = $1, cancellation_reason = $2, refund_amount = $3
         WHERE id = CAST($4 AS UUID)",
    )
    .bind(crate::time::Ts(&now))
    .bind(&reason)
    .bind(&refund_store)
    .bind(&hex)
    .execute(&st.db)
    .await?;
    if let Err(e) = crate::affiliate::utils::revoke_sale(&st.db, &hex, &now).await {
        tracing::error!("affiliate revoke failed: {e}");
    }

    if refund_cents > 0 && ticket.ticket_type_id.is_some() {
        // Raw balance bump (no ledger row), like Django.
        let next = m::raw_credit_balance(&st.db, user.id, refund_cents).await?;
        if let Some(tt_id) = &ticket.ticket_type_id {
            let _ = sqlx::query("UPDATE market_place_tickettype SET quantity_available = quantity_available + 1 WHERE id = CAST($1 AS UUID)")
                .bind(tt_id)
                .execute(&st.db)
                .await;
        }
        let canceled_at = crate::transactions::serializers::format_created_at_lagos(&now);
        return Ok((
            StatusCode::OK,
            Json(json!({
                "message": "Ticket canceled successfully",
                "state": true,
                "refund_amount": refund_store,
                "refund_policy": policy,
                "ticket_id": m::dashed(&hex),
                "canceled_at": canceled_at,
                "wallet_balance": crate::wallet::models::dec2(&next),
            })),
        ));
    }
    let canceled_at = crate::transactions::serializers::format_created_at_lagos(&now);
    Ok((
        StatusCode::OK,
        Json(json!({
            "message": "Free ticket canceled successfully",
            "state": true,
            "ticket_id": m::dashed(&hex),
            "canceled_at": canceled_at,
        })),
    ))
}
