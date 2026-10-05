//! User lookup + Paystack dedicated-virtual-account assignment.
//! Mirrors `accounts/views.py` `LookupUserView` + `DedicatedVirtualAccountAssignView`.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use regex::Regex;
use serde_json::{Value, json};

use crate::accounts::crypto as pin_crypto;
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
        sqlx::query_as("SELECT * FROM accounts_profile WHERE email = ?")
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
    summary = "Assign Wema dedicated virtual account",
    description = "Create single-step Paystack DVA for Wema Bank. Idempotent when one already exists.",
    request_body = DvaAssignBody,
    responses(
        (status = 200, description = "DVA already exists"),
        (status = 201, description = "Dedicated account assigned"),
        (status = 400, description = "Validation or Paystack failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn dva_assign(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(b): Json<DvaAssignBody>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    if user.has_dva {
        let existing: Option<DvaAccount> = sqlx::query_as(
            "SELECT * FROM accounts_paystackdedicatedaccount WHERE user_id = ?",
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
    if b.account_number.trim().is_empty() {
        return Err(AppError::bad_request("account_number is required"));
    }
    let re10 = Regex::new(r"^\d{10}$").unwrap();
    if !re10.is_match(b.account_number.trim()) {
        return Err(AppError::bad_request(
            "account_number must be 10 digits (NUBAN)",
        ));
    }
    if b.bank_code.trim().is_empty() {
        return Err(AppError::bad_request("bank_code is required"));
    }
    let re_bank = Regex::new(r"^\d{1,7}$").unwrap();
    if !re_bank.is_match(b.bank_code.trim()) {
        return Err(AppError::bad_request("bank_code must be 1-7 digits"));
    }
    if b.bvn.is_empty() {
        return Err(AppError::bad_request("bvn is required"));
    }
    let bvn_plain = pin_crypto::decrypt_pin(&b.bvn, &s.config.pin_rsa_private_key_b64)
        .map_err(|_| AppError::bad_request("Invalid encrypted bvn"))?;
    let re11 = Regex::new(r"^\d{11}$").unwrap();
    if !re11.is_match(&bvn_plain) {
        return Err(AppError::bad_request("bvn must be 11 digits"));
    }
    let phone = b.phone.clone().unwrap_or_default().trim().to_string();
    if phone.is_empty() {
        return Err(AppError::bad_request("phone is required"));
    }
    let re_phone = Regex::new(r"^\d{11}$").unwrap();
    let re_intl = Regex::new(r"^\+234\d{10,14}$").unwrap();
    if !re_phone.is_match(&phone) && !re_intl.is_match(&phone) {
        return Err(AppError::bad_request("phone must be 11 digits"));
    }
    let paystack_phone = if phone.starts_with('0') {
        format!("+234{}", &phone[1..])
    } else {
        phone.clone()
    };

    let payload = json!({
        "email": user.email, "first_name": b.first_name.trim(), "last_name": b.last_name.trim(),
        "phone": paystack_phone, "preferred_bank": "wema-bank", "country": "NG",
        "bvn": bvn_plain, "account_number": b.account_number.trim(), "bank_code": b.bank_code.trim(),
    });
    let resp = s
        .http
        .post("https://api.paystack.co/dedicated_account/assign")
        .bearer_auth(&s.config.paystack_secret_key)
        .json(&payload)
        .send()
        .await
        .map_err(|_| {
            AppError::new(
                StatusCode::BAD_GATEWAY,
                "Unable to contact Paystack, try again",
            )
        })?;
    let data: Value = resp.json().await.map_err(|_| {
        AppError::new(
            StatusCode::BAD_GATEWAY,
            "Unable to contact Paystack, try again",
        )
    })?;
    if data.get("status").and_then(|v| v.as_bool()) != Some(true) {
        let msg = data
            .get("message")
            .and_then(|v| v.as_str())
            .unwrap_or("Failed to assign dedicated account");
        return Err(AppError::bad_request(msg.to_string()));
    }
    let now = now_naive().to_string();
    let name = format!("{} {}", b.first_name.trim(), b.last_name.trim());
    sqlx::query(
        "INSERT INTO accounts_paystackdedicatedaccount (dedicated_account_id, account_number, account_name, bank_name, bank_slug, bank_id, customer_code, customer_id, phone, bvn_encrypted, active, paystack_response, created_at, updated_at, user_id, dva_account_name, dva_account_number)
         VALUES (NULL, ?, ?, 'Wema Bank', 'wema-bank', NULL, '', NULL, ?, ?, 1, '{}', ?, ?, ?, NULL, NULL)
         ON CONFLICT(user_id) DO UPDATE SET account_number=excluded.account_number, account_name=excluded.account_name, phone=excluded.phone, bvn_encrypted=excluded.bvn_encrypted, active=1, updated_at=excluded.updated_at")
        .bind(b.account_number.trim()).bind(&name).bind(&paystack_phone).bind(&b.bvn).bind(&now).bind(&now).bind(user.id)
        .execute(&s.db).await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({
            "status": true,
            "message": data.get("message").and_then(|v| v.as_str()).unwrap_or("Dedicated account assigned"),
            "has_DVA": false,
        })),
    ))
}
