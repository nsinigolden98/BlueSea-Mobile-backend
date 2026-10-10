//! Vendor endpoints. Mirrors `CreateTicketVendor`, `VendorStatusView`,
//! `VendorTicketsList` in `market_place/views.py`.

use axum::{
    Json,
    extract::{Query, Request, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::json;
use std::collections::HashMap;

use crate::error::AppError;
use crate::state::AppState;
use crate::time::now_str;

use super::{bad, forbidden, full_name, me, not_found, parse_body};
use super::Resp;
use crate::market_place::models as m;
use crate::market_place::serializers as s;
use crate::market_place::utils::store_upload;

const DOC_TYPES: &[&str] = &[
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
];

#[utoipa::path(
    post,
    path = "/marketplace/vendor/create/",
    tag = "Marketplace Vendors",
    summary = "Create ticket vendor account",
    description = "Create a vendor account for KYC review. Requires transaction PIN set. Multipart with id_document + proof_of_address uploads.",
    responses((status = 201, description = "Verification submitted"), (status = 400, description = "Invalid input"), (status = 500, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn create_vendor(
    State(st): State<AppState>,
    headers: HeaderMap,
    req: Request,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    if !user.pin_is_set {
        return Ok(bad("Please set your transaction PIN before creating a vendor account."));
    }
    if m::vendor_for_user(&st.db, user.id).await?.is_some() {
        return Ok(bad("You already have a ticket vendor account."));
    }
    let form = parse_body(req, 20 * 1024 * 1024).await?;
    let get = |k: &str| form.fields.get(k).map(|v| v.trim().to_string()).unwrap_or_default();
    let business_type = get("business_type");
    let brand_name = get("brand_name");
    let residential_address = get("residential_address");
    let state_city = get("state");
    let id_type = get("id_type");
    let monthly_volume = get("monthly_volume");
    let business_description = get("business_description");
    let mut missing = Vec::new();
    // Django reports the literal key `state_city` for the `state` input.
    for (label, value) in [
        ("business_type", &business_type),
        ("brand_name", &brand_name),
        ("residential_address", &residential_address),
        ("state_city", &state_city),
        ("id_type", &id_type),
        ("monthly_volume", &monthly_volume),
        ("business_description", &business_description),
    ] {
        if value.is_empty() {
            missing.push(label);
        }
    }
    if !missing.is_empty() {
        return Ok(bad(&format!("Missing required fields: {}", missing.join(", "))));
    }

    let id_doc = form.file("id_document");
    let poa = form.file("proof_of_address");
    let auth = form.file("event_authorization");
    let Some((_, id_ctype, id_bytes)) = id_doc else {
        return Ok(bad("ID document upload is required."));
    };
    let Some((_, poa_ctype, poa_bytes)) = poa else {
        return Ok(bad("Proof of address not uploaded"));
    };
    if !DOC_TYPES.contains(&id_ctype) {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Invalid ID document format. Allowed: PDF, JPEG, PNG", "success": false})),
        ));
    }
    if !DOC_TYPES.contains(&poa_ctype) {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Invalid proof of address format. Allowed: PDF, JPEG, PNG", "success": false})),
        ));
    }

    let categories_raw = get("categories");
    let categories: Vec<String> = categories_raw
        .split(',')
        .map(|c| c.trim().to_string())
        .filter(|c| !c.is_empty())
        .collect();
    let (state, city) = match state_city.split_once(':') {
        Some((a, b)) => (a.to_string(), b.to_string()),
        None => (state_city.clone(), String::new()),
    };

    let now = now_str();
    async fn store_doc(
        st: &AppState,
        tup: Option<(&str, &str, &[u8])>,
        dir: &str,
    ) -> Result<String, AppError> {
        match tup {
            Some((fname, _, bytes)) => {
                store_upload(&st.config.media_root, dir, fname, bytes, true)
                    .await
                    .map_err(AppError::bad_request)
            }
            None => Err(AppError::bad_request("missing file")),
        }
    }
    let id_document = store_doc(&st, id_doc, "vendor_ids").await?;
    let proof_of_address = store_doc(&st, poa, "vendor_proof_of_address").await?;
    let event_authorization = match auth {
        Some(_) => Some(store_doc(&st, auth, "vendor_event_auth").await?),
        None => None,
    };

    let categories_joined = categories.join(",");
    let vendor_id = m::new_id();
    let legal_full_name = full_name(&user);
    let insert = sqlx::query(
        "INSERT INTO market_place_ticketvendor
         (id, phone_number, email, brand_name, residential_address, state, city,
          is_verified, created_at, rejection_reason, business_description, business_type,
          categories, event_authorization, id_document, id_type, monthly_volume,
          proof_of_address, legal_full_name, user_id, updated_at, verification_status)
         VALUES (CAST($1 AS UUID), $2, $3, $4, $5, $6, $7, 0, $8, NULL, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, 'pending')",
    )
    .bind(&vendor_id)
    .bind(&user.phone)
    .bind(&user.email)
    .bind(&brand_name)
    .bind(&residential_address)
    .bind(&state)
    .bind(&city)
    .bind(crate::time::Ts(&now))
    .bind(&business_description)
    .bind(&business_type)
    .bind(&categories_joined)
    .bind(&event_authorization)
    .bind(&id_document)
    .bind(&id_type)
    .bind(&monthly_volume)
    .bind(&proof_of_address)
    .bind(&legal_full_name)
    .bind(user.id)
    .bind(crate::time::Ts(&now));
    if let Err(e) = insert.execute(&st.db).await {
        tracing::error!("vendor creation failed for user {}: {e}", user.id);
        let details = if user.is_staff { Some(e.to_string()) } else { None };
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": "Failed to submit verification request. Please try again.", "success": false, "details": details})),
        ));
    }
    let created_at = crate::transactions::serializers::format_created_at_lagos(&now);
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "success": true,
            "message": "Verification request submitted successfully. Our team will review within 24-72 hours.",
            "vendor": {
                "id": m::dashed(&vendor_id),
                "brand_name": brand_name,
                "verification_status": "pending",
                "created_at": created_at,
            },
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/vendor/status/",
    tag = "Marketplace Vendors",
    summary = "Get vendor verification status",
    responses((status = 200, description = "Vendor status"), (status = 404, description = "No vendor profile")),
    security(("bearer" = [])),
)]
pub async fn vendor_status(
    State(st): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = me(&st, headers).await?;
    let Some(v) = m::vendor_for_user(&st.db, user.id).await? else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"error": "No vendor profile found", "success": false})),
        ));
    };
    let created_at: Option<String> = sqlx::query_as("SELECT CAST(created_at AS TEXT) FROM market_place_ticketvendor WHERE id = CAST($1 AS UUID)")
        .bind(&v.id)
        .fetch_optional(&st.db)
        .await
        .ok()
        .flatten()
        .map(|r: (String,)| crate::transactions::serializers::format_created_at_lagos(&r.0));
    let updated_at: Option<String> = sqlx::query_as("SELECT CAST(updated_at AS TEXT) FROM market_place_ticketvendor WHERE id = CAST($1 AS UUID)")
        .bind(&v.id)
        .fetch_optional(&st.db)
        .await
        .ok()
        .flatten()
        .map(|r: (String,)| crate::transactions::serializers::format_created_at_lagos(&r.0));
    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "vendor": {
                "id": m::dashed(&v.id),
                "brand_name": v.brand_name,
                "business_type": v.business_type,
                "verification_status": v.verification_status,
                "is_verified": v.is_verified,
                "created_at": created_at,
                "updated_at": updated_at,
            },
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/marketplace/vendor/tickets/",
    tag = "Marketplace Vendors",
    summary = "Get all tickets from vendor's events",
    params(
        ("event_id" = Option<String>, Query, description = "Filter by event ID"),
        ("status" = Option<String>, Query, description = "Filter by ticket status"),
        ("search" = Option<String>, Query, description = "Search owner name or email"),
    ),
    responses((status = 200, description = "Vendor tickets"), (status = 403, description = "Not verified"), (status = 404, description = "No vendor profile")),
    security(("bearer" = [])),
)]
pub async fn vendor_tickets(
    State(st): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    let user = me(&st, headers.clone()).await?;
    let (scheme, host) = super::scheme_host(&headers);
    let Some(vendor) = m::vendor_for_user(&st.db, user.id).await? else {
        return Ok(not_found("Vendor profile not found"));
    };
    if !vendor.is_verified {
        return Ok(forbidden("Your vendor account is not verified"));
    }

    let event_filter = params.get("event_id").filter(|v| !v.is_empty()).and_then(|v| m::norm_id(v));
    if params.get("event_id").is_some_and(|v| !v.is_empty()) && event_filter.is_none() {
        // Unparseable event id matches nothing (Django would 400 on UUID
        // validation inside the filter; empty result is the safe mirror).
    }
    let status_filter = params.get("status").map(|v| v.as_str()).unwrap_or("all");
    let search = params.get("search").cloned().unwrap_or_default();

    let mut sql = "SELECT CAST(t.id AS TEXT) AS id, t.owner_name, t.owner_email, t.qr_code, t.status, t.created_at, CAST(t.event_id AS TEXT) AS event_id, t.purchased_by_id, t.canceled_at, t.cancellation_reason, t.qr_code_image, CAST(t.refund_amount AS TEXT) AS refund_amount, t.scanned_at, t.scanned_by_id, t.transfer_count, t.transferred_at, t.transferred_to, t.updated_at, CAST(t.ticket_type_id AS TEXT) AS ticket_type_id FROM market_place_issuedticket t JOIN market_place_eventinfo e ON e.id = t.event_id WHERE e.vendor_id = CAST($1 AS UUID)".to_string();
    let mut binds: Vec<String> = vec![vendor.id.clone()];
    let mut next_idx = 2i64;
    if let Some(ev) = &event_filter {
        sql.push_str(&format!(" AND t.event_id = ${next_idx}"));
        next_idx += 1;
        binds.push(ev.clone());
    }
    if status_filter != "all" {
        sql.push_str(&format!(" AND t.status = ${next_idx}"));
        next_idx += 1;
        binds.push(status_filter.to_string());
    }
    if !search.is_empty() {
        let like_ph: Vec<String> = (0..2).map(|_| { let s = format!("${next_idx}"); next_idx += 1; s }).collect();
        sql.push_str(&format!(" AND (t.owner_name LIKE {} ESCAPE '\\' OR t.owner_email LIKE {} ESCAPE '\\')", like_ph[0], like_ph[1]));
        let like = format!("%{}%", search.replace('\\', "\\\\").replace('%', "\\%").replace('_', "\\_"));
        binds.push(like.clone());
        binds.push(like);
    }
    sql.push_str(" ORDER BY t.created_at DESC");
    let mut q = sqlx::query_as::<_, m::IssuedTicket>(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    let tickets = q.fetch_all(&st.db).await?;

    // Statistics across ALL vendor tickets (unfiltered), like Django.
    // SUM yields NULL on empty sets, hence the Option decoding.
    let stats: (i64, Option<i64>, Option<i64>, Option<i64>, Option<i64>) = sqlx::query_as(
        "SELECT COUNT(*),
                SUM(CASE WHEN t.status = 'upcoming' THEN 1 ELSE 0 END),
                SUM(CASE WHEN t.status = 'used' THEN 1 ELSE 0 END),
                SUM(CASE WHEN t.status = 'expired' THEN 1 ELSE 0 END),
                SUM(CASE WHEN t.status = 'canceled' THEN 1 ELSE 0 END)
         FROM market_place_issuedticket t JOIN market_place_eventinfo e ON e.id = t.event_id
         WHERE e.vendor_id = CAST($1 AS UUID)",
    )
    .bind(&vendor.id)
    .fetch_one(&st.db)
    .await
    .unwrap_or((0, None, None, None, None));

    let vendor_events: Vec<m::EventInfo> = sqlx::query_as(
        &format!("SELECT {} FROM market_place_eventinfo WHERE vendor_id = CAST($1 AS UUID) ORDER BY event_date DESC", m::EVENTINFO_COLS),
    )
    .bind(&vendor.id)
    .fetch_all(&st.db)
    .await?;
    let mut events_out = Vec::new();
    for e in &vendor_events {
        events_out.push(s::event_public(&st.db, e, &scheme, &host).await);
    }

    Ok((
        StatusCode::OK,
        Json(json!({
            "state": true,
            "vendor": {"id": m::dashed(&vendor.id), "brand_name": vendor.brand_name},
            "statistics": {
                "total_tickets": stats.0,
                "upcoming": stats.1.unwrap_or(0),
                "used": stats.2.unwrap_or(0),
                "expired": stats.3.unwrap_or(0),
                "canceled": stats.4.unwrap_or(0),
            },
            "data": events_out,
        })),
    ))
}
