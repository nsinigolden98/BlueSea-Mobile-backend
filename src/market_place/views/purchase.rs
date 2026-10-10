//! Ticket purchase. Mirrors `PurchaseTicketView` in
//! `market_place/views.py` (free registration + paid wallet-debit flow).

use axum::{
    Json,
    extract::{Path, Request, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};

use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::{Resp, bad, full_name, me, not_found, parse_body, path_hex, scheme_host, verify_pin};
use crate::market_place::models as m;
use crate::market_place::serializers as s;
use crate::market_place::utils::render_qr_png;
use crate::notifications::utils::TicketMailRow;

fn reference_id() -> String {
    let now = chrono::Utc::now().format("%Y%m%d%H%M%S").to_string();
    let unique = uuid::Uuid::new_v4().simple().to_string()[..8].to_uppercase();
    format!("{now}-{unique}")
}

fn sales_open(event_date_utc_raw: &str) -> bool {
    let ts = crate::time::parse_stored_dt(event_date_utc_raw)
        .map(|dt| dt.and_utc().timestamp())
        .unwrap_or(i64::MAX);
    chrono::Utc::now().timestamp() <= ts + 4 * 3600
}

fn is_valid_email(v: &str) -> bool {
    let v = v.trim();
    match v.split_once('@') {
        Some((local, domain)) => !local.is_empty() && domain.contains('.') && !domain.starts_with('.') && !v.contains(' '),
        None => false,
    }
}

#[utoipa::path(
    post,
    path = "/marketplace/events/{event_id}/purchase/",
    tag = "Marketplace Tickets",
    summary = "Purchase event tickets",
    description = "Purchase tickets (paid events debit the wallet, PIN required) or register free tickets. Sales close 4hrs after event start.",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 201, description = "Tickets issued"), (status = 400, description = "Invalid input"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn purchase(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let hex = path_hex(&event_id).map_err(|_| AppError::not_found("Event not found"))?;
    let form = parse_body(req, 1024 * 1024).await?;

    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };

    // quantity: required int 1..=10 (DRF IntegerField messages).
    let qty_raw = form.fields.get("quantity").map(|v| v.trim().to_string()).unwrap_or_default();
    let quantity: i32 = if qty_raw.is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"quantity": ["This field is required."]}))));
    } else if let Ok(n) = qty_raw.parse::<i64>() {
        if n < 1 {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"quantity": ["Ensure this value is greater than or equal to 1."]}))));
        }
        if n > 10 {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"quantity": ["Ensure this value is less than or equal to 10."]}))));
        }
        n as i32
    } else {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"quantity": ["A valid integer is required."]}))));
    };

    let ticket_type_name = form.fields.get("ticket_type").map(|v| v.trim().to_string()).unwrap_or_default();
    let transaction_pin = form.fields.get("transaction_pin").map(|v| v.trim().to_string()).filter(|v| !v.is_empty());
    let affiliate_username = form.fields.get("affiliate_username").map(|v| v.trim().to_string()).filter(|v| !v.is_empty());
    if let Some(aff) = &affiliate_username {
        if aff.chars().count() > 13 {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"affiliate_username": ["Ensure this field has no more than 13 characters."]}))));
        }
    }

    // Ticket type resolution.
    let ticket_type = if event.is_free {
        if !ticket_type_name.is_empty() {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"ticket_type": ["Free events do not require a ticket type"]}))));
        }
        None
    } else {
        if ticket_type_name.is_empty() {
            return Ok((StatusCode::BAD_REQUEST, Json(json!({"ticket_type": ["Ticket type is required for paid events"]}))));
        }
        match m::ticket_type_by_name(&st.db, &hex, &ticket_type_name).await? {
            Some(tt) => Some(tt),
            None => {
                let available = m::ticket_types_for(&st.db, &hex).await.unwrap_or_default();
                let names: Vec<String> = available.iter().map(|t| t.name.clone()).collect();
                return Ok((StatusCode::BAD_REQUEST, Json(json!({"ticket_type": [format!("Ticket type '{ticket_type_name}' not found. Available types: {}", names.join(", "))]}))));
            }
        }
    };

    // Attendees: provided list or autofill.
    let attendees_raw = form.fields.get("attendees").map(|v| v.as_str()).unwrap_or("");
    let mut attendees: Vec<(String, String)> = Vec::new();
    let items: Option<Vec<Value>> = if attendees_raw.trim().is_empty() {
        None
    } else {
        let parsed: Value = serde_json::from_str(attendees_raw)
            .map_err(|_| AppError::bad_request("Invalid attendees format"))?;
        parsed.as_array().cloned()
    };
    match items {
        // Missing or explicitly empty list -> autofill with the buyer's
        // details (DRF `allow_empty` + `if not attendees` autofill).
        None => {
            let name = full_name(&user);
            for _ in 0..quantity {
                attendees.push((name.clone(), user.email.clone()));
            }
        }
        Some(list) if list.is_empty() => {
            let name = full_name(&user);
            for _ in 0..quantity {
                attendees.push((name.clone(), user.email.clone()));
            }
        }
        Some(list) => {
            if list.len() > 5 {
                return Ok((StatusCode::BAD_REQUEST, Json(json!({"attendees": ["Maximum 5 attendees per purchase"]})))); 
            }
            for item in &list {
                let name = item.get("name").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
                let email = item.get("email").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
                if name.is_empty() || name.chars().count() > 255 {
                    return Ok((StatusCode::BAD_REQUEST, Json(json!({"attendees": [{"name": ["This field is required."]}]})))); 
                }
                if !is_valid_email(&email) {
                    return Ok((StatusCode::BAD_REQUEST, Json(json!({"attendees": [{"email": ["Enter a valid email address."]}]})))); 
                }
                attendees.push((name, email));
            }
            if attendees.len() as i32 != quantity {
                return Ok((StatusCode::BAD_REQUEST, Json(json!({"attendees": [format!("Number of attendees ({}) must match quantity ({quantity})", attendees.len())]}))));
            }
        }
    }

    if event.is_canceled {
        return Ok(bad("This event has been canceled by the vendor"));
    }
    if !event.is_approved {
        return Ok(bad("This event is not yet approved for ticket sales"));
    }
    let event_date_raw = m::raw_event_date(&st.db, &hex).await.ok().flatten().unwrap_or_default();
    if !sales_open(&event_date_raw) {
        return Ok(bad("Ticket sales have closed for this event"));
    }

    if event.is_free {
        return purchase_free(&st, &user, &event, &event_date_raw, quantity, &attendees, &scheme, &host).await;
    }

    let tt = ticket_type.unwrap();
    let pin = match transaction_pin {
        Some(p) => p,
        None => return Ok(bad("Transaction PIN is required for paid events")),
    };
    // Fresh availability read (stock may have moved since validation).
    let fresh: Option<m::TicketType> = sqlx::query_as(&format!("SELECT {} FROM market_place_tickettype WHERE id = CAST($1 AS UUID)", m::TICKET_TYPE_COLS))
        .bind(&tt.id)
        .fetch_optional(&st.db)
        .await?;
    let (type_name_now, avail) = fresh
        .map(|t| (t.name, t.quantity_available))
        .unwrap_or_else(|| (tt.name.clone(), 0));
    if avail < quantity {
        return Ok(bad(&format!("Only {avail} tickets available for {type_name_now}")));
    }
    let price_cents = crate::wallet::models::parse_cents(&tt.price).unwrap_or(0);
    let total_cents = price_cents * quantity as i64;
    let wallet = match crate::wallet::models::get_by_user(&st.db, user.id).await? {
        Some(w) => w,
        None => {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Wallet not found. Please contact support.", "state": false})),
            ));
        }
    };
    if let Err(e) = verify_pin(&st, user.id, &pin).await {
        return Ok(e);
    }
    let balance_cents = crate::wallet::models::parse_cents(&wallet.balance).unwrap_or(0);
    if balance_cents < total_cents {
        return Ok(bad(&format!(
            "Insufficient balance. Required: {}, Available: {}",
            crate::wallet::models::format_naira(total_cents),
            crate::wallet::models::format_naira(balance_cents)
        )));
    }

    let reference = reference_id();
    let total_str = crate::wallet::models::cents_to_decimal(total_cents);
    let debit_res = crate::wallet::models::debit(
        &st.db,
        &st.wallet_hub,
        wallet.id,
        user.id,
        &total_str,
        &format!(" Bought {quantity} ticket for {} - {} - {}", event.event_title, event.event_title, tt.name),
        Some(&reference),
    )
    .await;
    let balances = match debit_res {
        Ok(b) => b,
        Err(e) => {
            tracing::error!("ticket purchase debit failed: {e:?}");
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"error": format!("Transaction failed: {e:?}"), "state": false})),
            ));
        }
    };
    let _ = sqlx::query("UPDATE market_place_tickettype SET quantity_available = quantity_available - $1 WHERE id = CAST($2 AS UUID)")
        .bind(quantity)
        .bind(&tt.id)
        .execute(&st.db)
        .await;

    let now = now_str();
    let mut issued: Vec<m::IssuedTicket> = Vec::new();
    for (name, email) in &attendees {
        let ticket_hex = m::new_id();
        let initial_qr = format!("{ticket_hex}:{tt_id}:{email}", ticket_hex = m::dashed(&ticket_hex), tt_id = m::dashed(&tt.id));
        sqlx::query(
            "INSERT INTO market_place_issuedticket
             (id, owner_name, owner_email, qr_code, status, created_at, event_id, purchased_by_id,
              canceled_at, cancellation_reason, qr_code_image, refund_amount, scanned_at, scanned_by_id,
              transfer_count, transferred_at, transferred_to, updated_at, ticket_type_id)
             VALUES (CAST($1 AS UUID), $2, $3, $4, 'upcoming', $5, CAST($6 AS UUID), $7, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, $8, CAST($9 AS UUID))",
        )
        .bind(&ticket_hex)
        .bind(name)
        .bind(email)
        .bind(&initial_qr)
        .bind(crate::time::Ts(&now))
        .bind(&hex)
        .bind(user.id)
        .bind(crate::time::Ts(&now))
        .bind(&tt.id)
        .execute(&st.db)
        .await?;
        finalize_qr(&st, &ticket_hex, &hex, &initial_qr).await;
        if let Some(t) = m::ticket_by_id(&st.db, &ticket_hex).await? {
            issued.push(t);
        }
    }

    if let Some(aff) = &affiliate_username {
        if let Ok(Some(ev)) = crate::affiliate::models::event_by_id(&st.db, &hex).await {
            let first_hex = issued.first().map(|t| t.id.clone());
            if let Err(e) = crate::affiliate::utils::complete_sale(&st.db, user.id, &ev, aff, first_hex.as_deref(), quantity, total_cents).await {
                tracing::error!("affiliate attribution failed: {e}");
            }
        }
    }

    let title = "Ticket Purchase Confirmed";
    let message = format!("You purchased {quantity} ticket(s) for '{}'. Total paid: ₦{total_str}.", event.event_title);
    let rows: Vec<TicketMailRow> = issued.iter().map(|t| TicketMailRow {
        owner_name: t.owner_name.clone(),
        ticket_type: tt.name.clone(),
        price: crate::wallet::models::dec2(&tt.price),
    }).collect();
    let _ = crate::notifications::utils::ticket_purchase_notification(
        &st, user.id, &user.email, &user.other_names, title, &message,
        &event.event_title, Some(&event_date_raw),
        &event.event_location.clone().unwrap_or_default(),
        &event.meeting_link.clone().unwrap_or_default(),
        &event.hosted_by, rows, quantity, &total_str, &reference,
    )
    .await;

    let mut tickets_out = Vec::new();
    for t in &issued {
        tickets_out.push(s::issued_ticket_out(&st.db, t, &scheme, &host).await);
    }
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "success": true,
            "message": format!("{quantity} {} ticket(s) purchased successfully for {}", tt.name, event.event_title),
            "tickets": tickets_out,
            "total_cost": total_str,
            "wallet_balance": balances.balance,
        })),
    ))
}

async fn purchase_free(
    st: &AppState,
    user: &crate::accounts::models::Profile,
    event: &m::EventInfo,
    event_date_raw: &str,
    quantity: i32,
    attendees: &[(String, String)],
    scheme: &str,
    host: &str,
) -> Result<Resp, AppError> {
    let sold = m::issued_count(&st.db, &event.id, true).await?;
    let remaining = event.quantity.unwrap_or(0) - sold;
    if remaining <= 0 {
        return Ok(bad("This event is fully booked"));
    }
    if quantity > remaining {
        return Ok(bad(&format!("Only {remaining} ticket(s) available")));
    }
    let now = now_str();
    let mut issued: Vec<m::IssuedTicket> = Vec::new();
    for (name, email) in attendees {
        let ticket_hex = m::new_id();
        let initial_qr = format!("{}:free-ticket:{email}", m::dashed(&ticket_hex));
        sqlx::query(
            "INSERT INTO market_place_issuedticket
             (id, owner_name, owner_email, qr_code, status, created_at, event_id, purchased_by_id,
              canceled_at, cancellation_reason, qr_code_image, refund_amount, scanned_at, scanned_by_id,
              transfer_count, transferred_at, transferred_to, updated_at, ticket_type_id)
             VALUES (CAST($1 AS UUID), $2, $3, $4, 'upcoming', $5, CAST($6 AS UUID), $7, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, $8, NULL)",
        )
        .bind(&ticket_hex)
        .bind(name)
        .bind(email)
        .bind(&initial_qr)
        .bind(crate::time::Ts(&now))
        .bind(&event.id)
        .bind(user.id)
        .bind(crate::time::Ts(&now))
        .execute(&st.db)
        .await?;
        finalize_qr(st, &ticket_hex, &event.id, &initial_qr).await;
        if let Some(t) = m::ticket_by_id(&st.db, &ticket_hex).await? {
            issued.push(t);
        }
    }
    let title = "Ticket Purchase Confirmed";
    let message = format!("You registered {quantity} free ticket(s) for '{}'. Your tickets are ready under My Tickets.", event.event_title);
    let rows: Vec<TicketMailRow> = issued.iter().map(|t| TicketMailRow {
        owner_name: t.owner_name.clone(),
        ticket_type: "Free Entry".to_string(),
        price: "0.00".to_string(),
    }).collect();
    let _ = crate::notifications::utils::ticket_purchase_notification(
        st, user.id, &user.email, &user.other_names, title, &message,
        &event.event_title, Some(event_date_raw),
        &event.event_location.clone().unwrap_or_default(),
        &event.meeting_link.clone().unwrap_or_default(),
        &event.hosted_by, rows, quantity, "0.00", "",
    )
    .await;
    let mut tickets_out = Vec::new();
    for t in &issued {
        tickets_out.push(s::issued_ticket_out(&st.db, t, scheme, host).await);
    }
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "success": true,
            "message": format!("{quantity} free ticket(s) registered successfully for {}", event.event_title),
            "tickets": tickets_out,
            "total_cost": "0.00",
        })),
    ))
}

/// Set the final HMAC-signed QR payload and PNG image, mirroring
/// `generate_ticket_qr_code` (image failure keeps the initial payload).
async fn finalize_qr(st: &AppState, ticket_hex: &str, event_hex: &str, fallback_qr: &str) {
    let ticket_dashed = m::dashed(ticket_hex);
    let event_dashed = m::dashed(event_hex);
    match render_qr_png(&st.config.media_root, &ticket_dashed, &event_dashed, &st.config.secret_key).await {
        Some((qr_data, stored)) => {
            let _ = sqlx::query("UPDATE market_place_issuedticket SET qr_code = $1, qr_code_image = $2 WHERE id = CAST($3 AS UUID)")
                .bind(&qr_data)
                .bind(&stored)
                .bind(ticket_hex)
                .execute(&st.db)
                .await;
        }
        None => {
            tracing::warn!("qr code image generation failed for ticket {ticket_hex}");
            let _ = sqlx::query("UPDATE market_place_issuedticket SET qr_code = $1 WHERE id = CAST($2 AS UUID)")
                .bind(fallback_qr)
                .bind(ticket_hex)
                .execute(&st.db)
                .await;
        }
    }
}
