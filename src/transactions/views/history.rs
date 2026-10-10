//! Wallet history. Mirrors `transactions/views.py::GetWalletTransaction`:
//! authenticated wallet lookup, `-created_at` ordering, DRF page-number
//! pagination (`?page=`, `?page_size=`, 5 default / 50 max).

use std::collections::HashMap;

use axum::{
    Json,
    extract::{Query, State},
    http::{HeaderMap, StatusCode, Uri},
};
use serde_json::json;

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::transactions::pagination::{Page, page_url};
use crate::transactions::serializers::WalletTransactionPublic;
use crate::wallet::models::get_by_user;

#[utoipa::path(
    get,
    path = "/transactions/history/",
    tag = "Wallet & Transactions",
    summary = "Get wallet transactions",
    description = "Retrieve all wallet transactions for the authenticated user, paginated",
    params(
        ("page" = Option<i64>, Query, description = "Page number (default 1)"),
        ("page_size" = Option<i64>, Query, description = "Page size (default 5, max 50)"),
    ),
    responses(
        (status = 200, description = "Paginated transactions"),
        (status = 404, description = "Wallet not found"),
    ),
    security(("bearer" = [])),
)]
pub async fn history(
    State(s): State<AppState>,
    headers: HeaderMap,
    uri: Uri,
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl axum::response::IntoResponse, AppError> {
    let user = auth_user(State(s.clone()), headers.clone()).await?;
    let Some(wallet) = get_by_user(&s.db, user.id).await? else {
        return Err(AppError {
            status: StatusCode::NOT_FOUND,
            message: "Wallet not found".into(),
        });
    };

    let page = Page::from_query(
        params.get("page").and_then(|v| v.parse().ok()),
        params.get("page_size").and_then(|v| v.parse().ok()),
    );
    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM transactions_wallettransaction WHERE wallet_id = $1",
    )
    .bind(wallet.id)
    .fetch_one(&s.db)
    .await?;
    let rows: Vec<(i64, i64, String, String, String, Option<String>, String, String)> = sqlx::query_as(
        "SELECT id, wallet_id, CAST(amount AS TEXT), transaction_type, status, description, reference, CAST(created_at AS TEXT)
         FROM transactions_wallettransaction WHERE wallet_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
    )
    .bind(wallet.id)
    .bind(page.size)
    .bind(page.offset())
    .fetch_all(&s.db)
    .await?;
    let results: Vec<WalletTransactionPublic> = rows
        .iter()
        .map(|(id, wallet_id, amount, tt, status, desc, reference, created_raw)| {
            WalletTransactionPublic::from_parts(
                *id,
                *wallet_id,
                amount,
                tt,
                status,
                desc.clone(),
                reference,
                created_raw,
            )
        })
        .collect();

    let host = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("localhost");
    let scheme = headers
        .get("x-forwarded-proto")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("http");
    let path = uri.path();
    let raw_query = uri.query().unwrap_or("");
    let total_pages = page.total_pages(count.0);
    let next = (page.number < total_pages).then(|| {
        page_url(scheme, host, path, raw_query, page.number + 1, page.size)
    });
    let previous = (page.number > 1).then(|| {
        page_url(
            scheme,
            host,
            path,
            raw_query,
            page.number - 1,
            page.size,
        )
    });

    Ok(Json(json!({
        "count": count.0,
        "next": next,
        "previous": previous,
        "results": results,
    })))
}
