//! User lookup + Nomba dedicated-virtual-account assignment.
//! Mirrors `accounts/views.py` `LookupUserView` + `DedicatedVirtualAccountAssignView`.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::json;

use crate::accounts::models::{DvaAccount, Profile};
use crate::accounts::serializers::{DvaAssignBody, LookupBody};
use crate::accounts::utils::now_naive;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;

#[utoipa::path(
    post,
    path = "/accounts/user/lookup/",
    tag = "Authentication",
    summary = "Lookup user by email",
    description = "Look up a user's public profile details by email",
    request_body = LookupBody,
    responses(
        (status = 200, description = "User found"),
        (status = 400, description = "Email parameter required"),
        (status = 404, description = "User not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn user_lookup(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<LookupBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let _me = auth_user(State(s.clone()), headers).await?;
    if b.email.is_empty() {
        return Err(AppError::bad_request("Email parameter is required"));
    }
    let user: Option<Profile> =
        sqlx::query_as("SELECT * FROM accounts_profile WHERE email = $1")
            .bind(&b.email)
            .fetch_optional(&s.db)
            .await?;
    match user {
        Some(u) => Ok(Json(json!({
            "found": true, "email": u.email,
            "name": format!("{} {}", u.other_names, u.surname).trim(),
            "image": u.image,
        }))),
        None => Err(AppError {
            status: StatusCode::NOT_FOUND,
            message: "User not found".into(),
        }),
    }
}

#[utoipa::path(
    post,
    path = "/accounts/dva/assign/",
    tag = "Authentication",
    summary = "Assign Nomba dedicated virtual account",
    description = "Create a Nomba DVA for the user. Idempotent when one already exists.",
    request_body = DvaAssignBody,
    responses(
        (status = 200, description = "DVA already exists"),
        (status = 201, description = "Dedicated account assigned"),
        (status = 400, description = "Validation or Nomba failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn dva_assign(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<DvaAssignBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    if let Some(e) = crate::accounts::models::find_nomba_dva_by_user(&s.db, user.id).await? {
        return Ok((
            StatusCode::OK,
            Json(json!({
                "already_exists": true,
                "account_number": e.account_number, "account_name": e.account_name,
                "bank_name": e.bank_name, "account_ref": e.account_ref,
                "active": e.active, "has_DVA": true,
            })),
        ));
    }
    if user.has_dva {
        let existing: Option<DvaAccount> = sqlx::query_as(
            "SELECT id, dedicated_account_id, account_number, account_name, bank_name, bank_slug, bank_id, customer_code, customer_id, phone, bvn_encrypted, active, CAST(paystack_response AS TEXT) AS paystack_response, created_at, updated_at, user_id, dva_account_name, dva_account_number FROM accounts_paystackdedicatedaccount WHERE user_id = $1",
        )
        .bind(user.id)
        .fetch_optional(&s.db)
        .await?;
        if let Some(e) = existing {
            return Ok((
                StatusCode::OK,
                Json(json!({
                    "already_exists": true,
                    "account_number": e.dva_account_number, "account_name": e.dva_account_name,
                    "bank_name": e.bank_name, "bank_slug": e.bank_slug, "bank_id": e.bank_id,
                    "customer_code": e.customer_code, "active": e.active, "has_DVA": true,
                })),
            ));
        }
    }
    if b.first_name.trim().is_empty() {
        return Err(AppError::bad_request("first_name is required"));
    }
    if b.last_name.trim().is_empty() {
        return Err(AppError::bad_request("last_name is required"));
    }
    // Nomba DVA needs only an account name; extra Paystack-era fields
    // (account_number, bank_code, bvn, phone) are accepted but ignored.
    // Paystack rails removed: DVA assignment runs on Nomba
    // (`create_virtual_account`), which needs no BVN/phone.
    let account_ref = format!("BS-NOMBA-DVA-{}", user.id);
    let (ok, result) = crate::transactions::nomba_gateway::create_virtual_account(
        &s.config, &account_ref, &format!("{} {}", b.first_name.trim(), b.last_name.trim()),
    )
    .await;
    if !ok {
        let msg = result.as_str().unwrap_or("Failed to assign dedicated account");
        return Err(AppError::new(StatusCode::BAD_GATEWAY, msg.to_string()));
    }
    let data = result;
    let now = now_naive().to_string();
    let name = format!("{} {}", b.first_name.trim(), b.last_name.trim());
    let account_number = data.get("bankAccountNumber").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let account_name = data.get("bankAccountName").and_then(|v| v.as_str()).unwrap_or(&name).to_string();
    let bank_name = data.get("bankName").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let active = !data.get("expired").and_then(|v| v.as_bool()).unwrap_or(false);
    sqlx::query(
        "INSERT INTO accounts_nombadedicatedaccount (user_id, account_ref, account_number, account_name, bank_name, active, nomba_response, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, CAST($7 AS JSONB), $8, $8)
         ON CONFLICT (user_id) DO UPDATE SET account_number=excluded.account_number, account_name=excluded.account_name, bank_name=excluded.bank_name, active=excluded.active, nomba_response=excluded.nomba_response, updated_at=excluded.updated_at")
        .bind(user.id).bind(&account_ref).bind(&account_number).bind(&account_name).bind(&bank_name).bind(active).bind(&data.to_string()).bind(crate::time::Ts(&now))
        .execute(&s.db).await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "status": true,
            "message": "Dedicated account assigned",
            "account_number": account_number,
            "account_name": account_name,
            "bank_name": bank_name,
            "has_DVA": false,
        })),
    ))
}
