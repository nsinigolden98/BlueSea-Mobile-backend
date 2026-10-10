//! Event endpoints. Mirrors `CreateEventView`, `EventListView`,
//! `EventDetailView`, `EventPublicView`, `EventUpdateView`,
//! `VendorEventCancelView`, `EventCancelStatusView`, `ExportAttendeesView`.

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

use super::{Resp, bad, bad_error, forbidden, me, not_found, parse_body, parse_event_date, path_hex, scheme_host};
use crate::market_place::models as m;
use crate::market_place::serializers as s;
use crate::market_place::utils::store_upload;

const CATEGORIES: &[&str] = &["Music", "Conference", "Sports", "Networking", "Workshop", "Party", "Others"];

fn str_bool(v: &str) -> bool {
    matches!(v.trim().to_lowercase().as_str(), "true" | "1" | "yes")
}

#[utoipa::path(
    post,
    path = "/marketplace/events/create/",
    tag = "Marketplace Events",
    summary = "Create a new event",
    description = "Create an event with ticket info. Only verified vendors. Multipart with event_banner (+ optional ticket_image) and ticket_types as a JSON string.",
    responses((status = 201, description = "Event created"), (status = 400, description = "Invalid input"), (status = 403, description = "Not a verified vendor")),
    security(("bearer" = [])),
)]
pub async fn create_event(
    State(st): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let vendor = m::vendor_for_user(&st.db, user.id).await?;
    let Some(vendor) = vendor else {
        return Ok(forbidden("Only verified vendors can create events. Please complete KYC verification."));
    };
    if !vendor.is_verified {
        return Ok(forbidden("Only verified vendors can create events. Please complete KYC verification."));
    }
    let form = parse_body(req, 30 * 1024 * 1024).await?;
    let get = |k: &str| form.fields.get(k).map(|v| v.trim().to_string()).unwrap_or_default();

    let is_free = str_bool(&get("is_free"));
    let mut ticket_types_data: Vec<Value> = vec![];
    let raw_tt = get("ticket_types");
    let trimmed = raw_tt.trim();
    if !is_free && !trimmed.is_empty() && !["[]", "", "null", "None"].contains(&trimmed) {
        match serde_json::from_str::<Value>(trimmed) {
            Ok(Value::Array(items)) => ticket_types_data = items,
            Ok(_) => {
                return Ok((
                    StatusCode::BAD_REQUEST,
                    Json(json!({"error": "ticket_types must be an array", "state": false})),
                ));
            }
            Err(e) => {
                return Ok((
                    StatusCode::BAD_REQUEST,
                    Json(json!({"error": format!("Invalid ticket_types JSON format: {e}"), "state": false})),
                ));
            }
        }
    }

    let event_title = get("event_title");
    let hosted_by = get("hosted_by");
    let category = get("category");
    let event_date_raw = get("event_date");
    // The model defaults `event_mode` to offline, so a missing mode behaves
    // as offline in Django (location required).
    let event_mode_input = get("event_mode");
    let event_mode = if event_mode_input.is_empty() { "offline".to_string() } else { event_mode_input };
    let event_location = get("event_location");
    let meeting_link = get("meeting_link");
    let event_description = get("event_description");
    let quantity_raw = get("quantity");

    // Field-level validation mirroring CreateEventSerializer.
    let mut errors = serde_json::Map::new();
    if event_title.is_empty() {
        errors.insert("event_title".into(), json!(["This field is required."]));
    }
    if hosted_by.is_empty() {
        errors.insert("hosted_by".into(), json!(["This field is required."]));
    }
    if !CATEGORIES.contains(&category.as_str()) {
        errors.insert("category".into(), json!([format!("\"{category}\" is not a valid choice.")]));
    }
    let Some((event_date, event_date_store)) = parse_event_date(&event_date_raw) else {
        errors.insert("event_date".into(), json!(["Datetime has wrong format."]));
        return Ok(bad_error(Value::Object(errors)));
    };
    if event_date.and_utc().timestamp() < chrono::Utc::now().timestamp() {
        errors.insert("event_date".into(), json!(["Event date must be in the future"]));
    }
    if is_free {
        match quantity_raw.parse::<i64>() {
            Ok(q) if q > 0 => {}
            _ => {
                errors.insert("quantity".into(), json!(["Quantity is required for free events"]));
            }
        }
        if !ticket_types_data.is_empty() {
            errors.insert("ticket_types".into(), json!(["Free events should not have ticket types"]));
        }
    } else {
        for (idx, tt) in ticket_types_data.iter().enumerate() {
            let name = tt.get("name").and_then(|v| v.as_str()).unwrap_or("");
            let qty = tt.get("quantity_available");
            let qty_num = qty.and_then(|v| v.as_i64()).or_else(|| qty.and_then(|v| v.as_str()).and_then(|v| v.parse::<i64>().ok()));
            match qty_num {
                None => {
                    errors.insert("ticket_types".into(), json!([format!("Ticket type {idx} ({name}): quantity_available is required")]));
                    break;
                }
                Some(q) if q <= 0 => {
                    errors.insert("ticket_types".into(), json!([format!("Ticket type {idx} ({name}): quantity_available must be greater than 0")]));
                    break;
                }
                _ => {}
            }
        }
    }
    match event_mode.as_str() {
        "offline" => {
            if event_location.is_empty() {
                errors.insert("event_location".into(), json!(["event_location is required for offline events"]));
            }
        }
        "online" => {
            if meeting_link.is_empty() {
                errors.insert("meeting_link".into(), json!(["meeting_link is required for online events"]));
            }
        }
        "hybrid" => {
            if event_location.is_empty() {
                errors.insert("event_location".into(), json!(["event_location is required for hybrid events"]));
            }
            if meeting_link.is_empty() {
                errors.insert("meeting_link".into(), json!(["meeting_link is required for hybrid events"]));
            }
        }
        _ => {
            errors.insert("event_mode".into(), json!(["event_mode must be 'offline', 'online' or 'hybrid'"]));
        }
    }
    // event_banner is required (ImageField, no blank=True).
    let banner = form.file("event_banner");
    if banner.is_none() {
        errors.insert("event_banner".into(), json!(["No file was submitted."]));
    }
    if !errors.is_empty() {
        return Ok(bad_error(Value::Object(errors)));
    }

    let (banner_name, _, banner_bytes) = banner.unwrap();
    let event_banner = store_upload(&st.config.media_root, "event_banners", banner_name, banner_bytes, false)
        .await
        .map_err(AppError::bad_request)?;
    let ticket_image = match form.file("ticket_image") {
        Some((fname, _, bytes)) => Some(store_upload(&st.config.media_root, "ticket_images", fname, bytes, false).await.map_err(AppError::bad_request)?),
        None => None,
    };

    let event_id = m::new_id();
    let now = now_str();
    let quantity: Option<i32> = if is_free { quantity_raw.parse::<i32>().ok() } else { None };
    let res = sqlx::query(
        "INSERT INTO market_place_eventinfo
         (id, event_title, hosted_by, category, event_banner, ticket_image, event_date,
          event_location, event_description, is_free, is_approved, created_at, vendor_id,
          quantity, event_mode, meeting_link,
          cancel_failed, cancel_processed, cancel_refunded, cancel_status, cancel_total,
          canceled_at, canceled_by_id, cancellation_reason, is_canceled)
         VALUES (CAST($1 AS UUID), $2, $3, $4, $5, $6, $7, $8, $9, $10, 0, $11, CAST($12 AS UUID), $13, $14, $15, 0, 0, 0, 'pending', 0, NULL, NULL, NULL, 0)",
    )
    .bind(&event_id)
    .bind(&event_title)
    .bind(&hosted_by)
    .bind(&category)
    .bind(&event_banner)
    .bind(&ticket_image)
    .bind(crate::time::Ts(&event_date_store))
    .bind(if event_location.is_empty() { None } else { Some(&event_location) })
    .bind(if event_description.is_empty() { None } else { Some(&event_description) })
    .bind(is_free)
    .bind(crate::time::Ts(&now))
    .bind(&vendor.id)
    .bind(quantity)
    .bind(&event_mode)
    .bind(if meeting_link.is_empty() { None } else { Some(&meeting_link) })
    .execute(&st.db)
    .await;
    if let Err(e) = res {
        tracing::error!("event creation failed: {e}");
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": format!("Failed to create event: {e}"), "state": false})),
        ));
    }
    for tt in &ticket_types_data {
        let name = tt.get("name").and_then(|v| v.as_str()).unwrap_or("General Admission").to_string();
        let price = tt.get("price").map(|v| v.as_str().unwrap_or("0").to_string()).unwrap_or_else(|| "0".to_string());
        let qty: i32 = tt.get("quantity_available").and_then(|v| v.as_i64()).and_then(|q| q.try_into().ok()).or_else(|| tt.get("quantity_available").and_then(|v| v.as_str()).and_then(|v| v.parse().ok())).unwrap_or(0);
        let description = tt.get("description").and_then(|v| v.as_str()).map(|v| v.to_string());
        let price_cents = crate::wallet::models::parse_cents(&price).unwrap_or(0);
        let price_store = crate::wallet::models::cents_to_decimal(price_cents);
        let _ = sqlx::query(
            "INSERT INTO market_place_tickettype (id, name, price, quantity_available, created_at, event_id, description, initial_quantity)
             VALUES (CAST($1 AS UUID), $2, CAST($3 AS NUMERIC), $4, $5, CAST($6 AS UUID), $7, $8)",
        )
        .bind(m::new_id())
        .bind(&name)
        .bind(&price_store)
        .bind(qty)
        .bind(crate::time::Ts(&now))
        .bind(&event_id)
        .bind(&description)
        .bind(qty)
        .execute(&st.db)
        .await;
    }
    let event = m::event_by_id(&st.db, &event_id).await?.ok_or_else(|| AppError::internal("Event not created"))?;
    let public = s::event_public(&st.db, &event, &scheme, &host).await;
    Ok((
        StatusCode::CREATED,
        Json(json!({"success": true, "message": "Event created successfully and pending approval", "event": public})),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/events/all/",
    tag = "Marketplace Events",
    summary = "List all approved events",
    params(("category" = Option<String>, Query, description = "Filter by category")),
    responses((status = 200, description = "Approved events")),
    security(("bearer" = [])),
)]
pub async fn list_events(
    State(st): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let _ = user;
    let (scheme, host) = scheme_host(&headers);
    let mut sql = format!("SELECT {} FROM market_place_eventinfo e WHERE e.is_approved = TRUE AND e.is_canceled = FALSE", crate::market_place::models::EVENTINFO_COLS);
    let category = params.get("category").cloned().unwrap_or_default();
    if !category.is_empty() {
        sql.push_str(" AND e.category = $1");
    }
    sql.push_str(" ORDER BY e.event_date DESC");
    let mut q = sqlx::query_as::<_, m::EventInfo>(&sql);
    if !category.is_empty() {
        q = q.bind(&category);
    }
    let events = q.fetch_all(&st.db).await?;
    let mut out = Vec::new();
    for e in &events {
        out.push(s::event_public(&st.db, e, &scheme, &host).await);
    }
    // DRF returns the bare list here.
    Ok((StatusCode::OK, Json(Value::Array(out.into_iter().map(|v| serde_json::to_value(v).unwrap_or(Value::Null)).collect()))))
}

async fn event_detail_inner(
    st: &AppState,
    scheme: &str,
    host: &str,
    event_hex: &str,
    approved_only: bool,
) -> Result<Resp, AppError> {
    let Some(event) = m::event_by_id(&st.db, event_hex).await? else {
        return Ok(not_found("Not found"));
    };
    if approved_only && (!event.is_approved || event.is_canceled) {
        return Ok(not_found("Not found"));
    }
    let public = s::event_public(&st.db, &event, scheme, host).await;
    Ok((StatusCode::OK, Json(serde_json::to_value(&public).unwrap_or(Value::Null))))
}

#[utoipa::path(
    get,
    path = "/marketplace/events/{event_id}/",
    tag = "Marketplace Events",
    summary = "Get event details",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 200, description = "Event detail"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn event_detail(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let _ = user;
    let (scheme, host) = scheme_host(&headers);
    let hex = path_hex(&event_id)?;
    event_detail_inner(&st, &scheme, &host, &hex, true).await
}

#[utoipa::path(
    get,
    path = "/marketplace/events/public/{event_id}/",
    tag = "Marketplace Events",
    summary = "Get public event details",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 200, description = "Event detail"), (status = 404, description = "Not found")),
)]
pub async fn event_public_view(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
) -> Result<Resp, AppError> {
    let (scheme, host) = scheme_host(&headers);
    let hex = path_hex(&event_id)?;
    event_detail_inner(&st, &scheme, &host, &hex, true).await
}

#[utoipa::path(
    patch,
    path = "/marketplace/events/{event_id}/edit/",
    tag = "Marketplace Events",
    summary = "Edit event info (vendor)",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 200, description = "Updated"), (status = 400, description = "Invalid input"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn update_event(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let hex = path_hex(&event_id)?;
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };
    let vendor = m::vendor_by_id(&st.db, &event.vendor_id).await?.ok_or_else(|| AppError::internal("Vendor missing"))?;
    let is_admin = user.is_staff || user.is_admin;
    let is_owner = vendor.user_id == Some(user.id);
    if !(is_owner || is_admin) {
        return Ok(forbidden("Only the event vendor can edit this event"));
    }
    if is_owner && !vendor.is_verified {
        return Ok(forbidden("Only verified vendors can edit events"));
    }
    if event.is_canceled {
        return Ok(bad("Canceled events cannot be edited"));
    }
    let event_ts = event.event_date.and_utc().timestamp();
    if event_ts < chrono::Utc::now().timestamp() {
        return Ok(bad("Events that have already started cannot be edited"));
    }

    let form = parse_body(req, 30 * 1024 * 1024).await?;
    // Only the six editable fields are honored.
    let mut updates: HashMap<String, String> = HashMap::new();
    for key in ["event_title", "event_location", "meeting_link", "event_date"] {
        if let Some(v) = form.fields.get(key) {
            updates.insert(key.to_string(), v.trim().to_string());
        }
    }
    let mut new_banner: Option<String> = None;
    let mut new_ticket_image: Option<String> = None;
    if let Some((fname, _, bytes)) = form.file("event_banner") {
        new_banner = Some(store_upload(&st.config.media_root, "event_banners", fname, bytes, false).await.map_err(AppError::bad_request)?);
    }
    if let Some((fname, _, bytes)) = form.file("ticket_image") {
        new_ticket_image = Some(store_upload(&st.config.media_root, "ticket_images", fname, bytes, false).await.map_err(AppError::bad_request)?);
    }
    if updates.is_empty() && new_banner.is_none() && new_ticket_image.is_none() {
        return Ok(bad("No editable fields provided"));
    }

    // Field validation mirroring EventUpdateSerializer.
    if let Some(raw) = updates.get("event_date") {
        match parse_event_date(raw) {
            Some((dt, _)) if dt.and_utc().timestamp() < chrono::Utc::now().timestamp() => {
                return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"event_date": ["Event date must be in the future"]}, "state": false}))));
            }
            None => {
                return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"event_date": ["Datetime has wrong format."]}, "state": false}))));
            }
            _ => {}
        }
    }
    let mode = event.event_mode.clone();
    let location = updates.get("event_location").cloned().or(event.event_location.clone()).unwrap_or_default();
    let link = updates.get("meeting_link").cloned().or(event.meeting_link.clone()).unwrap_or_default();
    if (mode == "offline" || mode == "hybrid") && location.trim().is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"event_location": ["event_location is required for this event mode"]}, "state": false}))));
    }
    if (mode == "online" || mode == "hybrid") && link.trim().is_empty() {
        return Ok((StatusCode::BAD_REQUEST, Json(json!({"error": {"meeting_link": ["meeting_link is required for this event mode"]}, "state": false}))));
    }

    // Material changes (old != new) for buyer mail + re-approval.
    let display_event_date = m::raw_event_date(&st.db, &hex).await.ok().flatten().unwrap_or_default();
    let mut material: HashMap<String, Value> = HashMap::new();
    if let Some(v) = updates.get("event_location") {
        let old = event.event_location.clone().unwrap_or_default();
        if old != *v {
            material.insert("event_location".into(), json!({"old": old, "new": v}));
        }
    }
    if let Some(v) = updates.get("meeting_link") {
        let old = event.meeting_link.clone().unwrap_or_default();
        if old != *v {
            material.insert("meeting_link".into(), json!({"old": old, "new": v}));
        }
    }
    if let Some(v) = updates.get("event_date") {
        let new_store = parse_event_date(v).map(|(_, s)| s).unwrap_or_default();
        // Compare instants, not strings: stored raws carry PG's "+00" suffix.
        let changed = match (
            crate::time::parse_stored_dt(&display_event_date),
            crate::time::parse_stored_dt(&new_store),
        ) {
            (Some(a), Some(b)) => a != b,
            _ => display_event_date != new_store,
        };
        if changed {
            material.insert("event_date".into(), json!({"old": display_event_date, "new": new_store}));
        }
    }

    let mut set: Vec<String> = Vec::new();
    let mut binds: Vec<String> = Vec::new();
    // PG placeholders are positional: number SET params in bind order.
    let mut next_idx = 1i64;
    let mut ph = || {
        let s = format!("${next_idx}");
        next_idx += 1;
        s
    };
    if let Some(v) = updates.get("event_title") {
        set.push(format!("event_title = {}", ph()));
        binds.push(v.clone());
    }
    if let Some(v) = updates.get("event_location") {
        set.push(format!("event_location = {}", ph()));
        binds.push(v.clone());
    }
    if let Some(v) = updates.get("meeting_link") {
        set.push(format!("meeting_link = {}", ph()));
        binds.push(v.clone());
    }
    if let Some(v) = updates.get("event_date") {
        set.push(format!("event_date = {}", ph()));
        binds.push(parse_event_date(v).map(|(_, s)| s).unwrap_or_default());
    }
    if let Some(b) = &new_banner {
        set.push(format!("event_banner = {}", ph()));
        binds.push(b.clone());
    }
    if let Some(t) = &new_ticket_image {
        set.push(format!("ticket_image = {}", ph()));
        binds.push(t.clone());
    }
    let reapproval = !material.is_empty();
    if reapproval {
        set.push("is_approved = FALSE".into());
    }
    if set.is_empty() {
        return Ok(bad("No editable fields provided"));
    }
    let where_idx = next_idx;
    let sql = format!("UPDATE market_place_eventinfo SET {} WHERE id = ${where_idx}", set.join(", "));
    let mut q = sqlx::query(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    q.bind(&hex).execute(&st.db).await?;

    if reapproval {
        let bg = st.clone();
        let event_hex = hex.clone();
        tokio::spawn(async move {
            crate::market_place::tasks::send_event_update_notifications(&bg, &event_hex, material).await;
        });
    }
    let locked = m::event_by_id(&st.db, &hex).await?.ok_or_else(|| AppError::internal("Event missing"))?;
    let public = s::event_public(&st.db, &locked, &scheme, &host).await;
    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "state": true,
            "message": if reapproval { "Event updated successfully and pending re-approval" } else { "Event updated successfully" },
            "reapproval_required": reapproval,
            "event": public,
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/marketplace/events/{event_id}/cancel/",
    tag = "Marketplace Events",
    summary = "Cancel a whole event (vendor)",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 202, description = "Queued"), (status = 200, description = "Already canceled"), (status = 400, description = "Invalid input"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn vendor_cancel(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let hex = path_hex(&event_id)?;
    let form = parse_body(req, 1024 * 1024).await?;
    let reason = form.fields.get("reason").map(|v| v.trim().to_string()).unwrap_or_default();
    if reason.is_empty() {
        return Ok(bad("Cancellation reason is required"));
    }
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };
    let vendor = m::vendor_by_id(&st.db, &event.vendor_id).await?.ok_or_else(|| AppError::internal("Vendor missing"))?;
    let is_admin = user.is_staff || user.is_admin;
    let is_owner = vendor.user_id == Some(user.id);
    if !(is_owner || is_admin) {
        return Ok(forbidden("Only the event vendor can cancel this event"));
    }
    if is_owner && !vendor.is_verified {
        return Ok(forbidden("Only verified vendors can cancel events"));
    }

    if event.is_canceled {
        let failed: i32 = event.cancel_failed;
        if event.cancel_status == "completed" && failed == 0 {
            return Ok((
                StatusCode::OK,
                Json(json!({
                    "success": true, "state": true,
                    "message": "Event is already canceled",
                    "event_id": m::dashed(&hex),
                    "cancel_status": event.cancel_status,
                    "refunded_count": event.cancel_refunded,
                })),
            ));
        }
        let bg = st.clone();
        let reason_clone = event.cancellation_reason.clone().unwrap_or(reason);
        tokio::spawn(async move {
            crate::market_place::tasks::process_event_cancellation(&bg, &hex, &reason_clone).await;
        });
        return Ok((
            StatusCode::ACCEPTED,
            Json(json!({
                "success": true, "state": true,
                "message": "Cancellation replay queued",
                "event_id": m::dashed(&event.id),
                "cancel_status": event.cancel_status,
            })),
        ));
    }

    if event.event_date.and_utc().timestamp() < chrono::Utc::now().timestamp() {
        return Ok(bad("This event has already passed"));
    }

    let mut funded_by = "platform";
    if is_owner {
        let pin = form.fields.get("transaction_pin").map(|v| v.as_str()).unwrap_or("");
        if pin.is_empty() {
            return Ok(bad("Transaction PIN is required to cancel an event"));
        }
        if let Err(e) = super::verify_pin(&st, user.id, pin).await {
            return Ok(e);
        }
        funded_by = "vendor";
    }

    // Totals over upcoming paid tickets.
    let upcoming: Vec<(String,)> = sqlx::query_as(
        "SELECT id FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID) AND status = 'upcoming'",
    )
    .bind(&hex)
    .fetch_all(&st.db)
    .await?;
    let total_cents: i64 = if event.is_free {
        0
    } else {
        let rows: Vec<(String,)> = sqlx::query_as(
            "SELECT CAST(tt.price AS TEXT) FROM market_place_issuedticket t
             JOIN market_place_tickettype tt ON tt.id = t.ticket_type_id
             WHERE t.event_id = CAST($1 AS UUID) AND t.status = 'upcoming' AND t.ticket_type_id IS NOT NULL",
        )
        .bind(&hex)
        .fetch_all(&st.db)
        .await?;
        rows.iter().filter_map(|r| crate::wallet::models::parse_cents(&r.0).ok()).sum()
    };

    if funded_by == "vendor" && total_cents > 0 {
        let vendor_uid = vendor.user_id.ok_or_else(|| AppError::internal("Vendor user missing"))?;
        let wallet = match crate::wallet::models::get_by_user(&st.db, vendor_uid).await? {
            Some(w) => w,
            None => {
                return Ok((
                    StatusCode::NOT_FOUND,
                    Json(json!({"error": "Vendor wallet not found. Please contact support.", "state": false})),
                ));
            }
        };
        let balance_cents = m::wallet_balance_cents(&st.db, vendor_uid).await?.unwrap_or(0);
        if balance_cents < total_cents {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({
                    "error": format!("Insufficient vendor balance to cover refunds. Required: {}, Available: {}",
                        crate::wallet::models::format_naira(total_cents), crate::wallet::models::format_naira(balance_cents)),
                    "state": false,
                    "required": crate::wallet::models::cents_to_decimal(total_cents),
                    "available": crate::wallet::models::cents_to_decimal(balance_cents),
                })),
            ));
        }
        let reference = format!("event-cancel-{}", m::dashed(&hex));
        if let Err(e) = crate::wallet::models::debit(
            &st.db,
            &st.wallet_hub,
            wallet.id,
            vendor_uid,
            &crate::wallet::models::cents_to_decimal(total_cents),
            &format!("Event cancellation payout: {}", event.event_title),
            Some(&reference),
        )
        .await
        {
            tracing::error!("vendor cancel debit failed: {e:?}");
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"error": format!("Cancellation failed: {e:?}"), "state": false})),
            ));
        }
    }

    let now = now_str();
    sqlx::query(
        "UPDATE market_place_eventinfo
         SET is_canceled = TRUE, canceled_at = $1, cancellation_reason = $2, canceled_by_id = $3,
             cancel_status = 'processing', cancel_total = $4, cancel_processed = 0,
             cancel_refunded = 0, cancel_failed = 0
         WHERE id = CAST($5 AS UUID)",
    )
    .bind(crate::time::Ts(&now))
    .bind(&reason)
    .bind(user.id)
    .bind(upcoming.len() as i64)
    .bind(&hex)
    .execute(&st.db)
    .await?;

    let bg = st.clone();
    tokio::spawn(async move {
        crate::market_place::tasks::process_event_cancellation(&bg, &hex, &reason).await;
    });
    Ok((
        StatusCode::ACCEPTED,
        Json(json!({
            "success": true, "state": true,
            "message": "Event canceled. Refunds and mails are being processed.",
            "event_id": m::dashed(&event.id),
            "tickets_queued": upcoming.len(),
            "total_refund": crate::wallet::models::cents_to_decimal(total_cents),
            "funded_by": funded_by,
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/events/{event_id}/cancel-status/",
    tag = "Marketplace Events",
    summary = "Get event cancellation status",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 200, description = "Cancel progress"), (status = 403, description = "Forbidden"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn cancel_status(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let hex = path_hex(&event_id)?;
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };
    let is_admin = user.is_staff || user.is_admin;
    let vendor = m::vendor_by_id(&st.db, &event.vendor_id).await?;
    if !(is_admin || vendor.and_then(|v| v.user_id) == Some(user.id)) {
        return Ok(forbidden("You do not have permission to view this"));
    }
    let canceled_at = sqlx::query_as::<_, (Option<String>,)>("SELECT CAST(canceled_at AS TEXT) FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)")
        .bind(&hex)
        .fetch_optional(&st.db)
        .await
        .ok()
        .flatten()
        .and_then(|r| r.0)
        .map(|r| crate::transactions::serializers::format_created_at_lagos(&r));
    Ok((
        StatusCode::OK,
        Json(json!({
            "event_id": m::dashed(&event.id),
            "is_canceled": event.is_canceled,
            "cancel_status": event.cancel_status,
            "cancel_total": event.cancel_total,
            "cancel_processed": event.cancel_processed,
            "cancel_refunded": event.cancel_refunded,
            "cancel_failed": event.cancel_failed,
            "canceled_at": canceled_at,
            "cancellation_reason": event.cancellation_reason,
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/events/{event_id}/attendees/export/",
    tag = "Marketplace Events",
    summary = "Export attendees",
    params(("event_id" = String, Path, description = "Event UUID"), ("format" = Option<String>, Query, description = "csv or txt")),
    responses((status = 200, description = "Attendee file"), (status = 400, description = "Bad format"), (status = 403, description = "Forbidden"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn export_attendees(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<axum::response::Response, AppError> {
    use axum::response::IntoResponse;
    let user = me(&st, headers).await?;
    let hex = path_hex(&event_id).map_err(|_| AppError::not_found("Event not found"))?;
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Err(AppError::not_found("Event not found"));
    };
    let vendor = m::vendor_by_id(&st.db, &event.vendor_id).await?.ok_or_else(|| AppError::internal("Vendor missing"))?;
    let mine = m::vendor_for_user(&st.db, user.id).await?.map(|v| v.id) == Some(vendor.id.clone());
    if !(user.is_staff || mine) {
        return Ok(forbidden("You do not have permission to export attendees for this event").into_response());
    }
    let export_format = params.get("format").map(|v| v.to_lowercase()).unwrap_or_else(|| "csv".to_string());
    let tickets: Vec<m::IssuedTicket> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID) ORDER BY created_at ASC", m::ISSUED_TICKET_COLS),
    )
    .bind(&hex)
    .fetch_all(&st.db)
    .await?;
    let stamp = chrono::Utc::now().format("%Y%m%d").to_string();
    // Sanitize the title for the filename (Django interpolates it raw).
    let safe_title: String = event.event_title.chars().filter(|c| !matches!(c, '"' | ';' | '\n' | '\r')).collect();
    if export_format == "csv" {
        let mut out = String::from("Name,Email,Ticket Type,Status,QR Code,Purchase Date\r\n");
        for t in &tickets {
            let type_name = match &t.ticket_type_id {
                Some(tt_id) => sqlx::query_as::<_, (String,)> ("SELECT name FROM market_place_tickettype WHERE id = $1")
                    .bind(tt_id)
                    .fetch_optional(&st.db)
                    .await
                    .ok()
                    .flatten()
                    .map(|r| r.0)
                    .unwrap_or_else(|| "Free".to_string()),
                None => "Free".to_string(),
            };
            let created: String = sqlx::query_as::<_, (String,)> ("SELECT CAST(created_at AS TEXT) FROM market_place_issuedticket WHERE id = $1")
                .bind(&t.id)
                .fetch_optional(&st.db)
                .await
                .ok()
                .flatten()
                .map(|r| m::utc_wall(&r.0))
                .unwrap_or_default();
            for cell in [&t.owner_name, &t.owner_email, &type_name, &t.status, &t.qr_code, &created] {
                out.push_str(&csv_cell(cell));
                out.push(',');
            }
            out.pop();
            out.push_str("\r\n");
        }
        let mut headers = HeaderMap::new();
        headers.insert("content-type", "text/csv".parse().unwrap());
        headers.insert("content-disposition", format!("attachment; filename=\"attendees_{safe_title}_{stamp}.csv\"").parse().unwrap());
        return Ok((StatusCode::OK, headers, out).into_response());
    }
    if export_format == "txt" {
        let event_date_raw: String = sqlx::query_as::<_, (String,)> ("SELECT CAST(event_date AS TEXT) FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)")
            .bind(&hex)
            .fetch_optional(&st.db)
            .await
            .ok()
            .flatten()
            .map(|r| m::utc_str(&r.0))
            .unwrap_or_default();
        let mut lines = vec![
            format!("Attendee List for: {}", event.event_title),
            format!("Event Date: {event_date_raw}"),
            format!("Event Mode: {}", mode_display(&event.event_mode)),
        ];
        if let Some(loc) = &event.event_location {
            lines.push(format!("Location: {loc}"));
        }
        if let Some(link) = &event.meeting_link {
            lines.push(format!("Meeting Link: {link}"));
        }
        lines.push("=".repeat(80));
        lines.push(String::new());
        for t in &tickets {
            let type_name = match &t.ticket_type_id {
                Some(tt_id) => sqlx::query_as::<_, (String,)> ("SELECT name FROM market_place_tickettype WHERE id = CAST($1 AS UUID)")
                    .bind(tt_id)
                    .fetch_optional(&st.db)
                    .await
                    .ok()
                    .flatten()
                    .map(|r| r.0)
                    .unwrap_or_else(|| "Free".to_string()),
                None => "Free".to_string(),
            };
            let created: String = sqlx::query_as::<_, (String,)> ("SELECT CAST(created_at AS TEXT) FROM market_place_issuedticket WHERE id = CAST($1 AS UUID)")
                .bind(&t.id)
                .fetch_optional(&st.db)
                .await
                .ok()
                .flatten()
                .map(|r| m::utc_wall(&r.0))
                .unwrap_or_default();
            lines.push(format!("Name: {}", t.owner_name));
            lines.push(format!("Email: {}", t.owner_email));
            lines.push(format!("Ticket Type: {type_name}"));
            lines.push(format!("Status: {}", t.status));
            lines.push(format!("QR Code: {}", t.qr_code));
            lines.push(format!("Purchase Date: {created}"));
            lines.push("-".repeat(80));
        }
        let mut headers = HeaderMap::new();
        headers.insert("content-type", "text/plain".parse().unwrap());
        headers.insert("content-disposition", format!("attachment; filename=\"attendees_{safe_title}_{stamp}.txt\"").parse().unwrap());
        return Ok((StatusCode::OK, headers, lines.join("\n")).into_response());
    }
    Ok(bad("Invalid format. Use 'csv' or 'txt'").into_response())
}

fn csv_cell(v: &str) -> String {
    if v.contains([',', '"', '\n', '\r']) {
        format!("\"{}\"", v.replace('"', "\"\""))
    } else {
        v.to_string()
    }
}

fn mode_display(mode: &str) -> &str {
    match mode {
        "offline" => "Offline",
        "online" => "Online",
        "hybrid" => "Hybrid",
        _ => mode,
    }
}
