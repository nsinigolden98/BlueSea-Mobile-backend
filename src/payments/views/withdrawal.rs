//! Bank withdrawals (Nomba rails).
//! The legacy Paystack route now delegates to `nomba_withdrawal::withdrawal`
//! (same request shape, Nomba bank transfer + webhook status).

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::Value;

use crate::error::AppError;
use crate::state::AppState;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    post,
    path = "/payments/withdrawal/",
    tag = "Withdrawal",
    summary = "Withdrawal via Nomba",
    description = "Withdraw wallet funds to a bank account via Nomba (minimum ₦500). DVA numbers route as internal transfers.",
    request_body = crate::payments::serializers::WithdrawalBody,
    responses(
        (status = 200, description = "Transfer successful or routed internal"),
        (status = 201, description = "Withdrawal submitted"),
        (status = 400, description = "Validation or funds failure"),
        (status = 500, description = "Transfer failed"),
    ),
    security(("bearer" = [])),
)]
pub async fn withdrawal(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    // Paystack rails removed: this route now runs on Nomba
    // (`payments/nomba_views.py::NombaWithdrawalView` equivalent).
    crate::payments::nomba_withdrawal::withdrawal(State(s), headers, Json(body)).await
}
