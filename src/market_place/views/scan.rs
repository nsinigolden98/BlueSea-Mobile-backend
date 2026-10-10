//! Scanner endpoints. Mirrors `ScanTicketView`, `ScannerDashboardView`,
//! `MyScannerAssignmentsView`, `AddEventScannerView`.
//!
//! The `20/min` DRF throttle becomes an in-process sliding window keyed by
//! user id (single-process semantics, same as Django-on-Daphne here).

use axum::{
    Json,
    extract::{Path, Request, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::{Resp, bad, forbidden, me, not_found, parse_body, path_hex, scheme_host};
use crate::market_place::models as m;
use crate::market_place::utils::parse_qr_data;

fn throttle_buckets() -> &'static Mutex<HashMap<i64, Vec<Instant>>> {
    static BUCKETS: OnceLock<Mutex<HashMap<i64, Vec<Instant>>>> = OnceLock::new();
    BUCKETS.get_or_init(|| Mutex::new(HashMap::new()))
}

/// 20 scans/minute sliding window. Returns seconds to wait when throttled.
fn throttle_check(user_id: i64) -> Option<u64> {
    let mut map = throttle_buckets().lock().unwrap();
    let now = Instant::now();
    let window = std::time::Duration::from_secs(60);
    let entry = map.entry(user_id).or_default();
    entry.retain(|t| now.duration_since(*t) < window);
    if entry.len() >= 20 {
        let oldest = entry.iter().min().unwrap();
        let wait = window.as_secs().saturating_sub(now.duration_since(*oldest).as_secs()).max(1);
        return Some(wait);
    }
    entry.push(now);
    None
}

#[utoipa::path(
    post,
    path = "/marketplace/tickets/scan/",
    tag = "Marketplace Scanner",
    summary = "Scan and validate ticket QR code",
    description = "Validate a ticket QR and mark it used. Requires scanner assignment, event ownership, or staff. Throttled to 20 scans/minute.",
    responses((status = 200, description = "Validated"), (status = 400, description = "Rejected"), (status = 403, description = "Not authorized"), (status = 404, description = "Not found"), (status = 429, description = "Throttled")),
    security(("bearer" = [])),
)]
pub async fn scan_ticket(
    State(st): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    if let Some(wait) = throttle_check(user.id) {
        return Ok((
            StatusCode::TOO_MANY_REQUESTS,
            Json(json!({"detail": format!("Request was throttled. Expected available in {wait} seconds.")})),
        ));
    }
    let form = parse_body(req, 1024 * 1024).await?;
    let qr_data = form.fields.get("qr_data").or_else(|| form.fields.get("qr_code")).map(|v| v.trim().to_string()).unwrap_or_default();
    if qr_data.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "qr_data is required", "state": false, "error_code": "MISSING_PARAMETERS"})),
        ));
    }
    let (ticket_part, event_part, _) = parse_qr_data(&qr_data, &st.config.secret_key);
    let Some(event_raw) = event_part else {
        // Unparseable QR: Django still looks up the event first (None id ->
        // DoesNotExist) and returns INVALID_EVENT.
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Event not found or not approved", "state": false, "error_code": "INVALID_EVENT"})),
        ));
    };
    let event_hex = m::dashed(&event_raw);
    let event: Option<m::EventInfo> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_eventinfo WHERE id = CAST($1 AS UUID) AND is_approved = TRUE", m::EVENTINFO_COLS),
    )
    .bind(&event_hex)
    .fetch_optional(&st.db)
    .await?;
    let Some(event) = event else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Event not found or not approved", "state": false, "error_code": "INVALID_EVENT"})),
        ));
    };
    if event.is_canceled {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "This event has been canceled", "state": false, "error_code": "CANCELED", "scan_result": "rejected"})),
        ));
    }
    let assigned: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM market_place_eventscanner WHERE user_id = $1 AND event_id = CAST($2 AS UUID)",
    )
    .bind(user.id)
    .bind(&event.id)
    .fetch_one(&st.db)
    .await?;
    let vendor = m::vendor_by_id(&st.db, &event.vendor_id).await.ok().flatten();
    let vendor_is_user = vendor.and_then(|v| v.user_id) == Some(user.id);
    if !(assigned.0 > 0 || vendor_is_user) {
        return Ok((
            StatusCode::FORBIDDEN,
            Json(json!({"error": "You are not authorized to scan tickets for this event", "state": false, "error_code": "UNAUTHORIZED_SCANNER"})),
        ));
    }

    let (ticket_part, qr_event_uuid, valid) = parse_qr_data(&qr_data, &st.config.secret_key);
    if !valid {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Invalid or tampered QR code", "state": false, "error_code": "INVALID_QR_CODE", "scan_result": "rejected"})),
        ));
    }
    if m::dashed(&event.id).to_lowercase() != qr_event_uuid.unwrap_or_default().to_lowercase() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "QR code is for a different event", "state": false, "error_code": "EVENT_MISMATCH", "scan_result": "rejected"})),
        ));
    }
    let ticket_hex = m::dashed(&ticket_part.unwrap_or_default());
    let Some(ticket) = m::ticket_by_id(&st.db, &ticket_hex).await? else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "Ticket not found", "state": false, "error_code": "TICKET_NOT_FOUND", "scan_result": "rejected"})),
        ));
    };

    if ticket.status == "used" {
        let (by_email, at): (Option<String>, Option<String>) = match ticket.scanned_by_id {
            Some(uid) => {
                let email = m::profile_email(&st.db, uid).await.ok().flatten().unwrap_or_else(|| "Unknown".to_string());
                let raw: Option<(Option<String>,)> = sqlx::query_as("SELECT CAST(scanned_at AS TEXT) FROM market_place_issuedticket WHERE id = CAST($1 AS UUID)")
                    .bind(&ticket.id)
                    .fetch_optional(&st.db)
                    .await
                    .ok()
                    .flatten();
                (Some(email), raw.and_then(|r| r.0).map(|r| m::utc_wall(&r)))
            }
            None => (Some("Unknown".to_string()), None),
        };
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error": "Ticket has already been used", "state": false, "error_code": "ALREADY_USED", "scan_result": "rejected",
                "ticket_details": {
                    "ticket_id": m::dashed(&ticket.id),
                    "owner_name": ticket.owner_name,
                    "owner_email": ticket.owner_email,
                    "status": ticket.status,
                    "scanned_by": by_email.unwrap_or_else(|| "Unknown".to_string()),
                    "scanned_at": at.unwrap_or_else(|| "Unknown".to_string()),
                },
            })),
        ));
    }
    if ticket.status == "expired" {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Ticket has expired", "state": false, "error_code": "EXPIRED", "scan_result": "rejected",
                "ticket_details": {"ticket_id": m::dashed(&ticket.id), "owner_name": ticket.owner_name, "status": ticket.status}})),
        ));
    }
    if ticket.status == "transferred" {
        let at: Option<String> = sqlx::query_as::<_, (Option<String>,)> ("SELECT CAST(transferred_at AS TEXT) FROM market_place_issuedticket WHERE id = CAST($1 AS UUID)")
            .bind(&ticket.id)
            .fetch_optional(&st.db)
            .await
            .ok()
            .flatten()
            .and_then(|r| r.0)
            .map(|r| m::utc_wall(&r));
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Ticket has been transferred to another user", "state": false, "error_code": "TRANSFERRED", "scan_result": "rejected",
                "ticket_details": {"ticket_id": m::dashed(&ticket.id), "transferred_to": ticket.transferred_to, "transferred_at": at}})),
        ));
    }
    if ticket.status == "canceled" {
        let at: Option<String> = sqlx::query_as::<_, (Option<String>,)> ("SELECT CAST(canceled_at AS TEXT) FROM market_place_issuedticket WHERE id = CAST($1 AS UUID)")
            .bind(&ticket.id)
            .fetch_optional(&st.db)
            .await
            .ok()
            .flatten()
            .and_then(|r| r.0)
            .map(|r| m::utc_wall(&r));
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Ticket has been canceled", "state": false, "error_code": "CANCELED", "scan_result": "rejected",
                "ticket_details": {"ticket_id": m::dashed(&ticket.id), "canceled_at": at}})),
        ));
    }

    let event_date_raw = m::raw_event_date(&st.db, &event.id).await.ok().flatten().unwrap_or_default();
    let event_ts = crate::time::parse_stored_dt(&event_date_raw)
        .map(|dt| dt.and_utc().timestamp())
        .unwrap_or(i64::MAX);
    let until = event_ts - chrono::Utc::now().timestamp();
    if until > 24 * 3600 {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error": format!("Event starts in {} hours. Early entry not allowed yet.", until / 3600),
                "state": false, "error_code": "TOO_EARLY", "scan_result": "rejected",
                "event_start": m::utc_wall(&event_date_raw),
            })),
        ));
    }

    let now = now_str();
    sqlx::query("UPDATE market_place_issuedticket SET status = 'used', scanned_at = $1, scanned_by_id = $2 WHERE id = CAST($3 AS UUID) AND status = 'upcoming'")
        .bind(crate::time::Ts(&now))
        .bind(user.id)
        .bind(&ticket.id)
        .execute(&st.db)
        .await?;
    // Lost the race (already flipped)? Re-read for the truthful branch.
    let current: Option<(String,)> = sqlx::query_as("SELECT status FROM market_place_issuedticket WHERE id = CAST($1 AS UUID)")
        .bind(&ticket.id)
        .fetch_optional(&st.db)
        .await?;
    if current.map(|r| r.0) != Some("used".to_string()) {
        return Ok(bad("Ticket could not be validated"));
    }
    let ticket_dict: Value = match &ticket.ticket_type_id {
        Some(tt_id) => {
            let row: Option<(String, String)> = sqlx::query_as("SELECT name, CAST(price AS TEXT) FROM market_place_tickettype WHERE id = CAST($1 AS UUID)")
                .bind(tt_id)
                .fetch_optional(&st.db)
                .await
                .ok()
                .flatten();
            match row {
                Some((name, price)) => json!({"name": name, "price": price.parse::<f64>().unwrap_or(0.0)}),
                None => Value::String("Free".to_string()),
            }
        }
        None => Value::String("Free".to_string()),
    };
    let vendor_name = m::vendor_by_id(&st.db, &event.vendor_id).await.ok().flatten().and_then(|v| v.brand_name);
    let purchased_by = match ticket.purchased_by_id {
        Some(uid) => m::profile_email(&st.db, uid).await.ok().flatten(),
        None => None,
    };
    Ok((
        StatusCode::OK,
        Json(json!({
            "message": "Ticket validated successfully",
            "state": true,
            "scan_result": "success",
            "ticket_details": {
                "ticket_id": m::dashed(&ticket.id),
                "owner_name": ticket.owner_name,
                "owner_email": ticket.owner_email,
                "ticket_type": ticket_dict,
                "event": {
                    "title": event.event_title,
                    "date": m::utc_wall(&event_date_raw),
                    "event_mode": event.event_mode,
                    "location": event.event_location,
                    "meeting_link": event.meeting_link,
                    "vendor": vendor_name,
                },
                "purchased_by": purchased_by,
                "status": "used",
                "scanned_at": m::utc_wall(&now),
                "scanned_by": user.email,
            },
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/events/{event_id}/scan-stats/",
    tag = "Marketplace Scanner",
    summary = "Get scanner dashboard statistics",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 200, description = "Scan stats"), (status = 403, description = "Not authorized"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn scan_stats(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let hex = path_hex(&event_id).map_err(|_| AppError::not_found("Event not found or not approved"))?;
    let event: Option<m::EventInfo> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_eventinfo WHERE id = CAST($1 AS UUID) AND is_approved = TRUE", m::EVENTINFO_COLS),
    )
    .bind(&hex)
    .fetch_optional(&st.db)
    .await?;
    let Some(event) = event else {
        return Ok(not_found("Event not found or not approved"));
    };
    let assigned: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM market_place_eventscanner WHERE user_id = $1 AND event_id = CAST($2 AS UUID)",
    )
    .bind(user.id)
    .bind(&event.id)
    .fetch_one(&st.db)
    .await?;
    let vendor = m::vendor_by_id(&st.db, &event.vendor_id).await.ok().flatten();
    if !(user.is_staff || assigned.0 > 0 || vendor.and_then(|v| v.user_id) == Some(user.id)) {
        return Ok(forbidden("You are not authorized to view this event's dashboard"));
    }
    let counts: (i64, Option<i64>, Option<i64>, Option<i64>, Option<i64>) = sqlx::query_as(
        "SELECT COUNT(*),
                SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'upcoming' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END)
         FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID)",
    )
    .bind(&event.id)
    .fetch_one(&st.db)
    .await
    .unwrap_or((0, None, None, None, None));
    let counts = (counts.0, counts.1.unwrap_or(0), counts.2.unwrap_or(0), counts.3.unwrap_or(0), counts.4.unwrap_or(0));
    let personal: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID) AND scanned_by_id = $2",
    )
    .bind(&event.id)
    .bind(user.id)
    .fetch_one(&st.db)
    .await
    .unwrap_or((0,));
    let recent: Vec<(String, String, Option<String>, String, Option<String>)> = sqlx::query_as(
        "SELECT CAST(t.id AS TEXT) AS id, t.owner_name, tt.name, CAST(t.scanned_at AS TEXT),
                (SELECT email FROM accounts_profile WHERE id = t.scanned_by_id)
         FROM market_place_issuedticket t LEFT JOIN market_place_tickettype tt ON tt.id = t.ticket_type_id
         WHERE t.event_id = CAST($1 AS UUID) AND t.status = 'used' ORDER BY t.scanned_at DESC LIMIT 20",
    )
    .bind(&event.id)
    .fetch_all(&st.db)
    .await
    .unwrap_or_default();
    let recent_out: Vec<Value> = recent
        .iter()
        .map(|(id, owner, tt_name, at, by)| {
            json!({
                "ticket_id": m::dashed(id).chars().take(8).collect::<String>(),
                "owner_name": owner,
                "ticket_type": tt_name.clone().unwrap_or_else(|| "Free".to_string()),
                "scanned_at": m::utc_wall(at.as_str()),
                "scanned_by": by.clone().unwrap_or_else(|| "Unknown".to_string()),
            })
        })
        .collect();
    // Note: Django crashes on free-ticket scans here (`None.name`); the
    // mirror defaults them to "Free" instead of 500ing.
    let event_date_raw = m::raw_event_date(&st.db, &event.id).await.ok().flatten().unwrap_or_default();
    let vendor_name = m::vendor_by_id(&st.db, &event.vendor_id).await.ok().flatten().and_then(|v| v.brand_name);
    let pct = |a: i64, b: i64| if b > 0 { ((a as f64 / b as f64) * 100.0 * 100.0).round() / 100.0 } else { 0.0 };
    Ok((
        StatusCode::OK,
        Json(json!({
            "state": true,
            "event": {
                "id": m::dashed(&event.id),
                "title": event.event_title,
                "date": m::utc_wall(&event_date_raw),
                "event_mode": event.event_mode,
                "location": event.event_location,
                "meeting_link": event.meeting_link,
                "vendor": vendor_name,
            },
            "statistics": {
                "total_issued": counts.0,
                "total_scanned": counts.1,
                "total_remaining": counts.2,
                "total_expired": counts.3,
                "total_canceled": counts.4,
                "scan_percentage": pct(counts.1, counts.0),
            },
            "personal_stats": {"scans_by_you": personal.0, "percentage_of_total": pct(personal.0, counts.1)},
            "recent_scans": recent_out,
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/my-scanner-assignments/",
    tag = "Marketplace Scanner",
    summary = "Get my scanner assignments",
    responses((status = 200, description = "Assigned events")),
    security(("bearer" = [])),
)]
pub async fn my_assignments(
    State(st): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = scheme_host(&headers);
    let assignments: Vec<m::EventScanner> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_eventscanner WHERE user_id = $1", m::SCANNER_COLS),
    )
    .bind(user.id)
    .fetch_all(&st.db)
    .await?;
    let mut out = Vec::new();
    for a in &assignments {
        let Some(event) = m::event_by_id(&st.db, &a.event_id).await? else { continue };
        if !event.is_approved {
            continue;
        }
        let (total, scanned): (i64, Option<i64>) = sqlx::query_as(
            "SELECT COUNT(*), SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END) FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID)",
        )
        .bind(&event.id)
        .fetch_one(&st.db)
        .await
        .unwrap_or((0, None));
        let scanned = scanned.unwrap_or(0);
        let created_raw: String = sqlx::query_as::<_, (String,)> ("SELECT CAST(created_at AS TEXT) FROM market_place_eventscanner WHERE id = CAST($1 AS UUID)")
            .bind(&a.id)
            .fetch_optional(&st.db)
            .await
            .ok()
            .flatten()
            .map(|r| m::utc_wall(&r.0))
            .unwrap_or_default();
        let event_date_raw = m::raw_event_date(&st.db, &event.id).await.ok().flatten().unwrap_or_default();
        let vendor_name = m::vendor_by_id(&st.db, &event.vendor_id).await.ok().flatten().and_then(|v| v.brand_name);
        let banner = if event.event_banner.is_empty() { None } else {
            Some(format!("{scheme}://{host}/media/{}", event.event_banner))
        };
        out.push(json!({
            "event_id": m::dashed(&event.id),
            "event_title": event.event_title,
            "event_date": m::utc_wall(&event_date_raw),
            "event_mode": event.event_mode,
            "event_location": event.event_location,
            "meeting_link": event.meeting_link,
            "event_banner": banner,
            "vendor": vendor_name,
            "role": "scanner",
            "statistics": {"total_tickets": total, "scanned_tickets": scanned, "remaining": total - scanned},
            "assigned_at": created_raw,
        }));
    }
    if let Some(vendor) = m::vendor_for_user(&st.db, user.id).await? {
        let owned: Vec<m::EventInfo> = sqlx::query_as(
            &format!("SELECT {} FROM market_place_eventinfo WHERE vendor_id = CAST($1 AS UUID) AND is_approved = TRUE", m::EVENTINFO_COLS),
        )
        .bind(&vendor.id)
        .fetch_all(&st.db)
        .await?;
        for event in &owned {
            let counts: (i64, Option<i64>) = sqlx::query_as(
                "SELECT COUNT(*), SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END) FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID)",
            )
            .bind(&event.id)
            .fetch_one(&st.db)
            .await
            .unwrap_or((0, None));
            let counts = (counts.0, counts.1.unwrap_or(0));
            let event_date_raw = m::raw_event_date(&st.db, &event.id).await.ok().flatten().unwrap_or_default();
            let banner = if event.event_banner.is_empty() { None } else {
                Some(format!("{scheme}://{host}/media/{}", event.event_banner))
            };
            out.push(json!({
                "event_id": m::dashed(&event.id),
                "event_title": event.event_title,
                "event_date": m::utc_wall(&event_date_raw),
                "event_mode": event.event_mode,
                "event_location": event.event_location,
                "meeting_link": event.meeting_link,
                "event_banner": banner,
                "vendor": vendor.brand_name,
                "role": "vendor",
                "statistics": {"total_tickets": counts.0, "scanned_tickets": counts.1, "remaining": counts.0 - counts.1},
            }));
        }
    }
    Ok((StatusCode::OK, Json(json!({"state": true, "count": out.len(), "events": out}))))
}

#[utoipa::path(
    post,
    path = "/marketplace/events/{event_id}/scanner/",
    tag = "Marketplace Scanner",
    summary = "Add scanner to event",
    params(("event_id" = String, Path, description = "Event UUID")),
    responses((status = 201, description = "Scanner added"), (status = 400, description = "Invalid input"), (status = 403, description = "Not the owner"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn add_scanner(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<String>,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let form = parse_body(req, 1024 * 1024).await?;
    let email_raw = form.fields.get("user_email").map(|v| v.as_str()).unwrap_or("");
    if email_raw.trim().is_empty() {
        return Ok(bad("user_email is required"));
    }
    let email_clean = email_raw.trim().to_string();
    let hex = path_hex(&event_id).map_err(|_| AppError::not_found("Event not found"))?;
    let Some(event) = m::event_by_id(&st.db, &hex).await? else {
        return Ok(not_found("Event not found"));
    };
    let vendor = m::vendor_for_user(&st.db, user.id).await?;
    let Some(vendor) = vendor else {
        return Ok(forbidden("Only vendors can add scanners"));
    };
    if vendor.id != event.vendor_id {
        return Ok(forbidden("You can only add scanners to your own events"));
    }
    let scanner: Option<(i64, String, String)> = sqlx::query_as(
        "SELECT id, email, role FROM accounts_profile WHERE LOWER(email) = LOWER($1)",
    )
    .bind(&email_clean)
    .fetch_optional(&st.db)
    .await?;
    let Some((scanner_id, scanner_email, scanner_role)) = scanner else {
        return Ok(not_found("User with this email not found"));
    };
    let existing: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM market_place_eventscanner WHERE user_id = $1 AND event_id = CAST($2 AS UUID)",
    )
    .bind(scanner_id)
    .bind(&event.id)
    .fetch_one(&st.db)
    .await?;
    if existing.0 > 0 {
        return Ok(bad("User is already assigned as scanner for this event"));
    }
    let now = now_str();
    let scanner_row_id = m::new_id();
    if let Err(e) = sqlx::query(
        "INSERT INTO market_place_eventscanner (id, created_at, event_id, user_id) VALUES (CAST($1 AS UUID), $2, CAST($3 AS UUID), $4)",
    )
    .bind(&scanner_row_id)
    .bind(crate::time::Ts(&now))
    .bind(&event.id)
    .bind(scanner_id)
    .execute(&st.db)
    .await
    {
        tracing::error!("add scanner failed: {e}");
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": "An unexpected error occurred while adding scanner", "state": false, "details": e.to_string()})),
        ));
    }
    if scanner_role == "user" {
        let _ = sqlx::query("UPDATE accounts_profile SET role = 'scanner' WHERE id = $1")
            .bind(scanner_id)
            .execute(&st.db)
            .await;
    }
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "message": format!("{scanner_email} added as scanner for {}", event.event_title),
            "state": true,
            "scanner": {
                "email": scanner_email,
                "event": event.event_title,
                "assigned_at": m::utc_wall(&now),
            },
        })),
    ))
}
