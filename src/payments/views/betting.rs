//! Betting-account funding (fund only — no bet placement).
//! Mirrors the Nomba purchase views: PIN gate → wallet debit →
//! `betting.vend_parent`, with the row persisted in
//! `payments_bettingpayment` (Django migration `0016_bettingpayment`).
//! Body: `{"provider", "customer_id", "amount", "phone_number"?,
//! "transaction_pin"}`.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::payments::models as pay_models;
use crate::payments::serializers::{req_amount_naira, req_str_max};
use crate::payments::views::common;
use crate::state::AppState;
use crate::transactions::nomba_gateway;
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/betting/fund/",
    tag = "Payments",
    summary = "Fund a betting account",
    description = "Fund a betting account via Nomba (fund only — no bet placement). Debited from the user wallet on success.",
    responses(
        (status = 200, description = "Nomba response"),
        (status = 400, description = "Validation, PIN or funds failure"),
    ),
    security(("bearer" = [])),
)]
pub async fn fund_betting(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = match common::pin_gate(&s, headers, &body, true).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };
    let provider = match req_str_max(&body, "provider", 60) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let customer_id = match req_str_max(&body, "customer_id", 50) {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let amount_naira = match req_amount_naira(&body, "amount") {
        Ok(v) => v,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    let phone = match body.get("phone_number") {
        None | Some(Value::Null) => user.phone.clone().unwrap_or_default(),
        Some(v) => match req_str_max(&body, "phone_number", 11) {
            Ok(p) => p,
            Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
        },
    };
    let amount_cents = crate::payments::serializers::naira_to_cents(amount_naira);

    let request_id = format!("BS-BET-{}", crate::payments::vtpass::generate_reference_id());
    let now = crate::time::now_str();
    if let Err(e) = pay_models::insert_betting(
        &s.db, user.id, &provider, &customer_id, amount_naira, &phone, &request_id, &now,
    )
    .await
    {
        return Ok(common::payment_failed(e));
    }

    let wallet = match wallet_models::get_by_user(&s.db, user.id).await {
        Ok(Some(w)) => w,
        Ok(None) => return Ok(common::payment_failed("Sender wallet not found")),
        Err(e) => return Ok(common::payment_failed(e)),
    };
    // Lock funds BEFORE the gateway call (double-spend guard).
    match wallet_models::lock_amount(&s.db, wallet.id, user.id, amount_cents, crate::accounts::tier::limit_cents(&user)).await {
        Ok(true) => {}
        Ok(false) => return Ok(common::insufficient_funds()),
        Err(e) => return Ok(common::lock_failed(e)),
    }

    let phone_opt = if phone.is_empty() { None } else { Some(phone.clone()) };
    let (ok, data) = nomba_gateway::fund_betting(
        &s.config, &provider, &customer_id, amount_naira, &request_id, phone_opt,
    )
    .await;
    if !ok {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
        let msg = data.as_str().unwrap_or("Betting funding failed").to_string();
        return Ok(common::payment_failed(msg));
    }
    let resp = serde_json::json!({
        "success": true,
        "code": "00",
        "description": "TRANSACTION SUCCESSFUL",
        "requestId": request_id,
        "reference": request_id,
        "data": data,
    });

    let desc = format!("BETTING: {} {} - ₦{amount_naira}", provider.to_uppercase(), common::last4(&customer_id));
    if let Err(e) = wallet_models::finalize_locked_debit(
        &s.db, &s.wallet_hub, wallet.id, user.id, amount_cents, &desc, &request_id,
    )
    .await
    {
        let _ = wallet_models::unlock_amount(&s.db, wallet.id, amount_cents).await;
        tracing::error!("betting funded but settle failed for {request_id}: {e:?}");
        return Ok(common::payment_failed(format!("{e:?}")));
    }
    common::settle_success(
        &s, &user, amount_cents, &request_id,
        "Betting Account Funded",
        &format!("₦{amount_naira} betting account funded for {customer_id}"),
        "BlueSea Mobile - Betting Funding",
    )
    .await;
    Ok((StatusCode::OK, Json(resp)))
}

/// Nomba betting providers list.
#[utoipa::path(
    get,
    path = "/payments/betting/providers/",
    tag = "Payments",
    summary = "List betting providers",
    responses((status = 200, description = "Providers")),
    security(("bearer" = [])),
)]
pub async fn betting_providers(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let _user = crate::auth::extractor::auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let (ok, data) = nomba_gateway::fetch_betting_providers(&s.config).await;
    if !ok {
        let msg = data.as_str().unwrap_or("Could not fetch providers").to_string();
        return Ok((StatusCode::BAD_REQUEST, Json(serde_json::json!({"success": false, "error": msg}))));
    }
    Ok((StatusCode::OK, Json(serde_json::json!({"success": true, "providers": data}))))
}

/// Nomba electricity (disco) providers list.
#[utoipa::path(
    get,
    path = "/payments/electricity/providers/",
    tag = "Payments",
    summary = "List electricity providers",
    responses((status = 200, description = "Providers")),
    security(("bearer" = [])),
)]
pub async fn electricity_providers(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let _user = crate::auth::extractor::auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let (ok, data) = nomba_gateway::fetch_electricity_providers(&s.config).await;
    if !ok {
        let msg = data.as_str().unwrap_or("Could not fetch providers").to_string();
        return Ok((StatusCode::BAD_REQUEST, Json(serde_json::json!({"success": false, "error": msg}))));
    }
    Ok((StatusCode::OK, Json(serde_json::json!({"success": true, "providers": data}))))
}

#[cfg(test)]
mod tests {
    use crate::payments::models as pay_models;

    async fn memory_db() -> sqlx::PgPool {
        crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, password varchar(128) NOT NULL,
             last_login TIMESTAMPTZ NULL, is_superuser BOOLEAN NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined TIMESTAMPTZ NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active BOOLEAN NOT NULL,
             is_staff BOOLEAN NOT NULL, is_admin BOOLEAN NOT NULL, role varchar(200) NOT NULL, email_verified BOOLEAN NOT NULL,
             created_on TIMESTAMPTZ NOT NULL, pin_is_set BOOLEAN NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until TIMESTAMPTZ NULL, nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL, utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE, frozen_reason varchar(200) NULL, \"has_DVA\" BOOLEAN NOT NULL)",
            "CREATE TABLE payments_bettingpayment (id BIGSERIAL PRIMARY KEY, provider varchar(50) NOT NULL,
             customer_id varchar(50) NOT NULL, amount integer NOT NULL, phone_number varchar(11) NOT NULL,
             request_id varchar(50) NULL UNIQUE, status varchar(20) NOT NULL DEFAULT 'pending',
             created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, user_id bigint NOT NULL,
             vtpass_transaction_id varchar(100) NULL)",
        ])
        .await
    }

    #[tokio::test]
    async fn insert_betting_roundtrip() {
        let db = memory_db().await;
        let now = crate::time::now_str();
        let id = pay_models::insert_betting(&db, 1, "MSPORT", "12345", 500, "0801", "BS-BET-1", &now)
            .await
            .unwrap();
        assert!(id > 0);
        let row: (String, String, String) = sqlx::query_as(
            "SELECT provider, customer_id, status FROM payments_bettingpayment WHERE id = $1",
        )
        .bind(id)
        .fetch_one(&db)
        .await
        .unwrap();
        assert_eq!((row.0.as_str(), row.1.as_str(), row.2.as_str()), ("MSPORT", "12345", "pending"));
        // request_id uniqueness is enforced.
        assert!(pay_models::insert_betting(&db, 1, "MSPORT", "12345", 500, "0801", "BS-BET-1", &now).await.is_err());
    }
}
