//! Admin models for `market_place`. Generated from the live Postgres schema.
use super::{ColType, ModelDef, PkType};
use axum::{
    Json,
    extract::{Path, State},
};

pub fn register(out: &mut Vec<ModelDef>) {
    out.push(ModelDef {
        name: "market_place.EventInfo",
        label: "Event Info",
        table: "market_place_eventinfo",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("event_title", ColType::Text),
        ("hosted_by", ColType::Text),
        ("category", ColType::Text),
        ("event_banner", ColType::Text),
        ("ticket_image", ColType::Text),
        ("event_date", ColType::DateTime),
        ("event_location", ColType::Text),
        ("event_description", ColType::Text),
        ("is_free", ColType::Bool),
        ("is_approved", ColType::Bool),
        ("created_at", ColType::DateTime),
        ("vendor_id", ColType::Uuid),
        ("quantity", ColType::Int),
        ("event_mode", ColType::Text),
        ("meeting_link", ColType::Text),
        ("cancel_failed", ColType::Int),
        ("cancel_processed", ColType::Int),
        ("cancel_refunded", ColType::Int),
        ("cancel_status", ColType::Text),
        ("cancel_total", ColType::Int),
        ("canceled_at", ColType::DateTime),
        ("canceled_by_id", ColType::Int),
        ("cancellation_reason", ColType::Text),
        ("is_canceled", ColType::Bool),
        ],
        search: &["event_title"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "market_place.EventScanner",
        label: "Event Scanner",
        table: "market_place_eventscanner",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("created_at", ColType::DateTime),
        ("event_id", ColType::Uuid),
        ("user_id", ColType::Int),
        ],
        search: &[],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "market_place.EventWithdrawal",
        label: "Event Withdrawal",
        table: "market_place_eventwithdrawal",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("amount", ColType::Numeric),
        ("status", ColType::Text),
        ("payment_reference", ColType::Text),
        ("created_at", ColType::DateTime),
        ("completed_at", ColType::DateTime),
        ("event_id", ColType::Uuid),
        ("amount_credited", ColType::Numeric),
        ("platform_fee", ColType::Numeric),
        ],
        search: &["payment_reference"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "market_place.IssuedTicket",
        label: "Issued Ticket",
        table: "market_place_issuedticket",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("owner_name", ColType::Text),
        ("owner_email", ColType::Text),
        ("qr_code", ColType::Text),
        ("status", ColType::Text),
        ("created_at", ColType::DateTime),
        ("event_id", ColType::Uuid),
        ("purchased_by_id", ColType::Int),
        ("ticket_type_id", ColType::Uuid),
        ("canceled_at", ColType::DateTime),
        ("cancellation_reason", ColType::Text),
        ("qr_code_image", ColType::Text),
        ("refund_amount", ColType::Numeric),
        ("scanned_at", ColType::DateTime),
        ("scanned_by_id", ColType::Int),
        ("transfer_count", ColType::Int),
        ("transferred_at", ColType::DateTime),
        ("transferred_to", ColType::Text),
        ("updated_at", ColType::DateTime),
        ],
        search: &["owner_name", "owner_email", "qr_code", "qr_code_image"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "market_place.TicketType",
        label: "Ticket Type",
        table: "market_place_tickettype",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("name", ColType::Text),
        ("price", ColType::Numeric),
        ("quantity_available", ColType::Int),
        ("created_at", ColType::DateTime),
        ("event_id", ColType::Uuid),
        ("description", ColType::Text),
        ("initial_quantity", ColType::Int),
        ],
        search: &["name"],
        default_order: "-created_at",
    });
    out.push(ModelDef {
        name: "market_place.TicketVendor",
        label: "Ticket Vendor",
        table: "market_place_ticketvendor",
        pk: "id",
        pk_type: PkType::Uuid,
        columns: &[
        ("id", ColType::Uuid),
        ("legal_full_name", ColType::Text),
        ("phone_number", ColType::Text),
        ("email", ColType::Text),
        ("brand_name", ColType::Text),
        ("residential_address", ColType::Text),
        ("state", ColType::Text),
        ("city", ColType::Text),
        ("is_verified", ColType::Bool),
        ("created_at", ColType::DateTime),
        ("rejection_reason", ColType::Text),
        ("business_description", ColType::Text),
        ("business_type", ColType::Text),
        ("categories", ColType::Text),
        ("event_authorization", ColType::Text),
        ("id_document", ColType::Text),
        ("id_type", ColType::Text),
        ("monthly_volume", ColType::Text),
        ("proof_of_address", ColType::Text),
        ("updated_at", ColType::DateTime),
        ("user_id", ColType::Int),
        ("verification_status", ColType::Text),
        ],
        search: &["legal_full_name", "phone_number", "email", "brand_name"],
        default_order: "-created_at",
    });
}

/// Vendor approve/reject (replaces Django's `reject_vendors_with_reason`
/// admin view). Staff-gated; routes wired in `super::router`.
pub async fn approve_vendor(
    State(s): State<crate::state::AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<String>,
) -> super::Resp {
    let _admin = match super::require_staff(&s, headers).await {
        Ok(u) => u,
        Err(e) => return e,
    };
    let Some(uuid) = crate::market_place::models::norm_id(&id) else {
        return (axum::http::StatusCode::NOT_FOUND, axum::Json(serde_json::json!({"detail": "Not found."})));
    };
    let res = sqlx::query(
        "UPDATE market_place_ticketvendor SET is_verified = TRUE, verification_status = 'approved',
                rejection_reason = NULL, updated_at = $1 WHERE id = CAST($2 AS UUID)",
    )
    .bind(crate::time::Ts(&crate::time::now_str()))
    .bind(&uuid)
    .execute(&s.db)
    .await;
    match res {
        Ok(r) if r.rows_affected() > 0 => (
            axum::http::StatusCode::OK,
            axum::Json(serde_json::json!({"success": true})),
        ),
        Ok(_) => (
            axum::http::StatusCode::NOT_FOUND,
            axum::Json(serde_json::json!({"detail": "Not found."})),
        ),
        Err(e) => super::err_json(crate::error::AppError::internal(format!("Approve failed: {e}"))),
    }
}

pub async fn reject_vendor(
    State(s): State<crate::state::AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> super::Resp {
    let _admin = match super::require_staff(&s, headers).await {
        Ok(u) => u,
        Err(e) => return e,
    };
    let reason = body
        .get("reason")
        .and_then(|v| v.as_str())
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty());
    let Some(reason) = reason else {
        return (
            axum::http::StatusCode::BAD_REQUEST,
            axum::Json(serde_json::json!({"detail": "Rejection reason is required."})),
        );
    };
    let Some(uuid) = crate::market_place::models::norm_id(&id) else {
        return (axum::http::StatusCode::NOT_FOUND, axum::Json(serde_json::json!({"detail": "Not found."})));
    };
    let res = sqlx::query(
        "UPDATE market_place_ticketvendor SET is_verified = FALSE, verification_status = 'rejected',
                rejection_reason = $1, updated_at = $2 WHERE id = CAST($3 AS UUID)",
    )
    .bind(&reason)
    .bind(crate::time::Ts(&crate::time::now_str()))
    .bind(&uuid)
    .execute(&s.db)
    .await;
    match res {
        Ok(r) if r.rows_affected() > 0 => (
            axum::http::StatusCode::OK,
            axum::Json(serde_json::json!({"success": true})),
        ),
        Ok(_) => (
            axum::http::StatusCode::NOT_FOUND,
            axum::Json(serde_json::json!({"detail": "Not found."})),
        ),
        Err(e) => super::err_json(crate::error::AppError::internal(format!("Reject failed: {e}"))),
    }
}
