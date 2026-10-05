//! Wallet REST handlers. Mirrors `wallet/views.py::WalletBalance`:
//! formatted naira strings, 404 `{"error": ...}` when no wallet exists.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::json;

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;

use super::models::{format_naira, get_by_user, parse_cents};

#[utoipa::path(
    get,
    path = "/wallet/balance/",
    tag = "Wallet",
    summary = "Get wallet balance",
    description = "Return the user's wallet balance, locked balance and available balance as formatted naira strings",
    responses(
        (status = 200, description = "Balance returned"),
        (status = 404, description = "Wallet not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn balance(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers).await?;
    let Some(wallet) = get_by_user(&s.db, user.id).await? else {
        return Err(AppError {
            status: StatusCode::NOT_FOUND,
            message: "Wallet not found.".into(),
        });
    };
    // Single lookup, no N+1 (mirrors the query-count test in Django).
    let balance_cents = parse_cents(&wallet.balance)
        .map_err(|_| AppError::internal("Corrupt wallet balance"))?;
    let locked_cents = parse_cents(&wallet.locked_balance)
        .map_err(|_| AppError::internal("Corrupt wallet balance"))?;
    Ok(Json(json!({
        "balance": format_naira(balance_cents),
        "locked_balance": format_naira(locked_cents),
        "available_balance": format_naira(balance_cents),
    })))
}
