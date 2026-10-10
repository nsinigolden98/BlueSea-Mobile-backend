//! Payment status lookup. Mirrors
//! `payments/views.py::PaymentStatusView`: search the 14 VTU tables (owner
//! check), then group payments (initiator or member), then internal
//! transfers (owner only), with ownership failures masked as 404.

use axum::{Json, extract::{Path, State}, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::state::AppState;
use crate::transactions::serializers::format_created_at_lagos;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    get,
    path = "/payments/status/{reference_id}/",
    tag = "Payments",
    summary = "Get payment status by reference_id",
    description = "Retrieve VTpass payment status using reference_id. The user must own the transaction.",
    params(("reference_id" = String, Path, description = "Reference ID (BS-...)")),
    responses((status = 200, description = "Status returned"), (status = 404, description = "Not found")),
    security(("bearer" = [])),
)]
pub async fn payment_status(
    State(s): State<AppState>,
    headers: HeaderMap,
    Path(reference_id): Path<String>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;

    if let Some(found) = pay_models::find_by_request_id(&s.db, &reference_id).await? {
        if found.user_id != Some(user.id) {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Not found"})),
            ));
        }
        let stamps = purchase_stamps(&s, found.model_name, found.id).await?;
        return Ok((
            StatusCode::OK,
            Json(json!({
                "reference_id": reference_id,
                "status": found.status,
                "vtpass_transaction_id": found.vtpass_transaction_id,
                "type": found.model_name,
                "created_at": stamps.0,
                "updated_at": stamps.1,
            })),
        ));
    }

    if let Some(gp) = group_status_row(&s, &reference_id).await? {
        let (id, status, vtu_ref, created_raw, updated_raw, initiated_by, group_id) = gp;
        let allowed = initiated_by == Some(user.id) || is_group_member(&s, &group_id, user.id).await?;
        if !allowed {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Not found"})),
            ));
        }
        let _ = id;
        return Ok((
            StatusCode::OK,
            Json(json!({
                "reference_id": vtu_ref.unwrap_or(reference_id),
                "status": status,
                "type": "GroupPayment",
                "created_at": format_created_at_lagos(&created_raw),
                "updated_at": format_created_at_lagos(&updated_raw),
            })),
        ));
    }

    if let Some((row, owner)) = pay_models::find_internal_transfer(&s.db, &reference_id).await? {
        if owner != user.id {
            return Ok((
                StatusCode::NOT_FOUND,
                Json(json!({"error": "Not found"})),
            ));
        }
        return Ok((
            StatusCode::OK,
            Json(json!({
                "reference_id": row.reference_id,
                "status": row.status,
                "type": "InternalTransfer",
                // Quirk: updated_at echoes completed_at, like Django.
                "created_at": format_created_at_lagos(&row.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()),
                "updated_at": row.completed_at.as_ref().map(|dt| {
                    format_created_at_lagos(&dt.format("%Y-%m-%d %H:%M:%S%.f").to_string())
                }),
            })),
        ));
    }

    Ok((
        StatusCode::NOT_FOUND,
        Json(json!({"error": "Reference not found"})),
    ))
}

async fn purchase_stamps(
    s: &AppState,
    model_name: &str,
    id: i64,
) -> Result<(String, String), AppError> {
    let table = match model_name {
        "AirtimeTopUp" => "payments_airtimetopup",
        "MTNDataTopUp" => "payments_mtndatatopup",
        "AirtelDataTopUp" => "payments_airteldatatopup",
        "GloDataTopUp" => "payments_glodatatopup",
        "EtisalatDataTopUp" => "payments_etisalatdatatopup",
        "DSTVPayment" => "payments_dstvpayment",
        "GOTVPayment" => "payments_gotvpayment",
        "StartimesPayment" => "payments_startimespayment",
        "ShowMaxPayment" => "payments_showmaxpayment",
        "ElectricityPayment" => "payments_electricitypayment",
        "WAECRegitration" => "payments_waecregitration",
        "WAECResultChecker" => "payments_waecresultchecker",
        "JAMBRegistration" => "payments_jambregistration",
        _ => "payments_airtime2cash",
    };
    let row: Option<(String, String)> = sqlx::query_as(&format!(
        "SELECT CAST(created_at AS TEXT), CAST(updated_at AS TEXT) FROM {table} WHERE id = $1"
    ))
    .bind(id)
    .fetch_optional(&s.db)
    .await?;
    match row {
        Some((c, u)) => Ok((
            format_created_at_lagos(&c),
            format_created_at_lagos(&u),
        )),
        None => Ok((String::new(), String::new())),
    }
}

async fn group_status_row(
    s: &AppState,
    reference_id: &str,
) -> Result<
    Option<(i64, String, Option<String>, String, String, Option<i64>, String)>,
    AppError,
> {
    let row: Option<(i64, String, Option<String>, String, String, Option<i64>, String)> =
        sqlx::query_as(
            "SELECT id, status, vtpass_transaction_id, CAST(created_at AS TEXT), CAST(updated_at AS TEXT),
                    initiated_by_id, group_id
             FROM payments_grouppayment
             WHERE vtu_reference = $1 OR service_details ->> 'request_id' = $2",
        )
        .bind(reference_id)
        .bind(reference_id)
        .fetch_optional(&s.db)
        .await?;
    Ok(row)
}

async fn is_group_member(s: &AppState, group_id: &str, user_id: i64) -> Result<bool, AppError> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM group_payment_groupmember WHERE group_id = CAST($1 AS UUID) AND user_id = $2",
    )
    .bind(group_id)
    .bind(user_id)
    .fetch_optional(&s.db)
    .await?;
    Ok(row.is_some())
}
