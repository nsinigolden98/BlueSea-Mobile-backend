//! Ledger rows. Mirrors `transactions/models.py::WalletTransaction`
//! (`wallet`, `amount`, `CREDIT`/`DEBIT`, default `COMPLETED`,
//! `description`, unique `reference`, `-created_at` ordering).

use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct WalletTransaction {
    pub id: i64,
    pub wallet_id: i64,
    pub amount: String,
    pub transaction_type: String,
    pub status: String,
    pub description: Option<String>,
    pub reference: String,
    pub created_at: crate::time::NaiveUtc,
}

#[derive(Debug, Clone, FromRow)]
pub struct FundWallet {
    pub id: i64,
    pub amount: String,
    pub payment_reference: String,
    pub gateway_reference: Option<String>,
    pub status: String,
    pub created_at: crate::time::NaiveUtc,
    pub completed_at: Option<crate::time::NaiveUtc>,
    pub user_id: i64,
}

pub async fn reference_exists(
    db: &sqlx::PgPool,
    reference: &str,
) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM transactions_wallettransaction WHERE reference = $1")
            .bind(reference)
            .fetch_optional(db)
            .await?;
    Ok(row.is_some())
}

/// A DEBIT ledger row exists for `reference` (drives webhook idempotency).
pub async fn debit_exists(db: &sqlx::PgPool, reference: &str) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM transactions_wallettransaction WHERE reference = $1 AND transaction_type = 'DEBIT'",
    )
    .bind(reference)
    .fetch_optional(db)
    .await?;
    Ok(row.is_some())
}

pub async fn find_pending_funding(
    db: &sqlx::PgPool,
    payment_reference: &str,
) -> Result<Option<FundWallet>, sqlx::Error> {
    sqlx::query_as::<_, FundWallet>(
        "SELECT id, CAST(amount AS TEXT) AS amount, payment_reference, gateway_reference, status, created_at, completed_at, user_id
         FROM transactions_fundwallet WHERE payment_reference = $1 AND status = 'PENDING'",
    )
    .bind(payment_reference)
    .fetch_optional(db)
    .await
}

pub async fn create_pending_funding(
    db: &sqlx::PgPool,
    user_id: i64,
    amount_cents: i64,
    payment_reference: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO transactions_fundwallet (amount, payment_reference, gateway_reference, status, created_at, completed_at, user_id)
         VALUES (CAST($1 AS NUMERIC), $2, NULL, 'PENDING', $3, NULL, $4)",
    )
    .bind(crate::wallet::models::cents_to_decimal(amount_cents))
    .bind(payment_reference)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn reference_exists_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    reference: &str,
) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM transactions_wallettransaction WHERE reference = $1")
            .bind(reference)
            .fetch_optional(&mut **tx)
            .await?;
    Ok(row.is_some())
}

pub async fn record_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    wallet_id: i64,
    amount_cents: i64,
    transaction_type: &str,
    description: &str,
    reference: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    record_tx_str(
        tx,
        wallet_id,
        &crate::wallet::models::cents_to_decimal(amount_cents),
        transaction_type,
        description,
        reference,
        now,
    )
    .await
}

pub async fn record_tx_str(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    wallet_id: i64,
    amount_display: &str,
    transaction_type: &str,
    description: &str,
    reference: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO transactions_wallettransaction (wallet_id, amount, transaction_type, status, description, reference, created_at)
         VALUES ($1, CAST($2 AS NUMERIC), $3, 'COMPLETED', $4, $5, $6)",
    )
    .bind(wallet_id)
    .bind(amount_display)
    .bind(transaction_type)
    .bind(description)
    .bind(reference)
    .bind(crate::time::Ts(&now))
    .execute(&mut **tx)
    .await?;
    Ok(())
}
