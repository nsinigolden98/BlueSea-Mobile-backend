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
    pub created_at: chrono::NaiveDateTime,
}

pub async fn reference_exists(
    db: &sqlx::SqlitePool,
    reference: &str,
) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM transactions_wallettransaction WHERE reference = ?")
            .bind(reference)
            .fetch_optional(db)
            .await?;
    Ok(row.is_some())
}

pub async fn reference_exists_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Sqlite>,
    reference: &str,
) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> =
        sqlx::query_as("SELECT id FROM transactions_wallettransaction WHERE reference = ?")
            .bind(reference)
            .fetch_optional(&mut **tx)
            .await?;
    Ok(row.is_some())
}

pub async fn record_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Sqlite>,
    wallet_id: i64,
    amount_cents: i64,
    transaction_type: &str,
    description: &str,
    reference: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO transactions_wallettransaction (wallet_id, amount, transaction_type, status, description, reference, created_at)
         VALUES (?, ?, ?, 'COMPLETED', ?, ?, ?)",
    )
    .bind(wallet_id)
    .bind(crate::wallet::models::cents_to_decimal(amount_cents))
    .bind(transaction_type)
    .bind(description)
    .bind(reference)
    .bind(now)
    .execute(&mut **tx)
    .await?;
    Ok(())
}
