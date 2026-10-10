//! Auto top-up rows. Mirrors `autotopup/models.py`:
//! schedule + wallet locking (`lock_funds`/`unlock_funds` move money
//! directly, with no ledger rows) and execution history.

use rust_decimal::Decimal;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct AutoTopUpRow {
    pub id: i64,
    pub service_type: String,
    pub amount: String,
    pub phone_number: String,
    pub network: Option<String>,
    pub plan: Option<String>,
    pub start_date: crate::time::NaiveUtc,
    pub repeat_days: i32,
    pub is_active: bool,
    pub next_run: crate::time::NaiveUtc,
    pub is_locked: bool,
    pub locked_amount: String,
    pub last_run: Option<crate::time::NaiveUtc>,
    pub total_runs: i32,
    pub failed_runs: i32,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub user_id: i64,
}

#[derive(Debug, Clone, FromRow)]
pub struct AutoTopUpHistoryRow {
    pub id: i64,
    pub amount: String,
    pub status: String,
    pub vtu_reference: Option<String>,
    pub vtu_response: Option<String>,
    pub error_message: Option<String>,
    pub executed_at: crate::time::NaiveUtc,
    pub auto_topup_id: i64,
}

pub fn dec(raw: &str) -> Decimal {
    raw.parse::<Decimal>().unwrap_or(Decimal::ZERO)
}

const COLS: &str = "id, service_type, CAST(amount AS TEXT) AS amount, phone_number, network, plan,
        start_date, repeat_days, is_active, next_run, is_locked, CAST(locked_amount AS TEXT) AS locked_amount,
        last_run, total_runs, failed_runs, created_at, updated_at, user_id";

pub async fn get_for_user(
    db: &sqlx::PgPool,
    id: i64,
    user_id: i64,
) -> Result<Option<AutoTopUpRow>, sqlx::Error> {
    sqlx::query_as::<_, AutoTopUpRow>(&format!(
        "SELECT {COLS} FROM autotopup_autotopup WHERE id = $1 AND user_id = $2"
    ))
    .bind(id)
    .bind(user_id)
    .fetch_optional(db)
    .await
}

pub async fn list_for_user(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Vec<AutoTopUpRow>, sqlx::Error> {
    sqlx::query_as::<_, AutoTopUpRow>(&format!(
        "SELECT {COLS} FROM autotopup_autotopup WHERE user_id = $1 ORDER BY created_at DESC"
    ))
    .bind(user_id)
    .fetch_all(db)
    .await
}

pub async fn due_topups(db: &sqlx::PgPool, now: &str) -> Result<Vec<i64>, sqlx::Error> {
    sqlx::query_as::<_, (i64,)>(
        "SELECT id FROM autotopup_autotopup WHERE is_active = TRUE AND next_run <= $1 AND is_locked = TRUE ORDER BY id",
    )
    .bind(crate::time::Ts(&now))
    .fetch_all(db)
    .await
    .map(|rows| rows.into_iter().map(|(id,)| id).collect())
}

/// Move `amount` from balance to locked_balance. Returns false when short.
pub async fn lock_funds(
    db: &sqlx::PgPool,
    user_id: i64,
    topup_id: i64,
    amount: Decimal,
    now: &str,
) -> Result<bool, sqlx::Error> {
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Ok(false);
    };
    let balance = dec(&balance_raw);
    if balance < amount {
        return Ok(false);
    }
    let locked = dec(&locked_raw) + amount;
    sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), locked_balance = CAST($2 AS NUMERIC), updated_at = $3 WHERE user_id = $4")
        .bind((balance - amount).to_string())
        .bind(locked.to_string())
        .bind(crate::time::Ts(&now))
        .bind(user_id)
        .execute(db)
        .await?;
    sqlx::query(
        "UPDATE autotopup_autotopup SET is_locked = TRUE, locked_amount = CAST($1 AS NUMERIC), updated_at = $2 WHERE id = $3",
    )
    .bind(amount.to_string())
    .bind(crate::time::Ts(&now))
    .bind(topup_id)
    .execute(db)
    .await?;
    Ok(true)
}

/// Move locked funds back to balance. Returns false when nothing to unlock.
pub async fn unlock_funds(
    db: &sqlx::PgPool,
    user_id: i64,
    topup_id: i64,
    now: &str,
) -> Result<bool, sqlx::Error> {
    let topup = get_for_user(db, topup_id, user_id).await?;
    let Some(t) = topup else {
        return Ok(false);
    };
    let locked_amount = dec(&t.locked_amount);
    if !t.is_locked || locked_amount <= Decimal::ZERO {
        return Ok(false);
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await?;
    if let Some((balance_raw, locked_raw)) = row {
        let balance = dec(&balance_raw) + locked_amount;
        let locked = dec(&locked_raw) - locked_amount;
        sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), locked_balance = CAST($2 AS NUMERIC), updated_at = $3 WHERE user_id = $4")
            .bind(balance.to_string())
            .bind(locked.to_string())
            .bind(crate::time::Ts(&now))
            .bind(user_id)
            .execute(db)
            .await?;
    }
    sqlx::query(
        "UPDATE autotopup_autotopup SET is_locked = FALSE, locked_amount = '0.00', updated_at = $1 WHERE id = $2",
    )
    .bind(crate::time::Ts(&now))
    .bind(topup_id)
    .execute(db)
    .await?;
    Ok(true)
}

pub async fn insert_history(
    db: &sqlx::PgPool,
    topup_id: i64,
    amount: &str,
    status: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO autotopup_autotopuphistory (auto_topup_id, amount, status, vtu_reference, vtu_response, error_message, executed_at)
         VALUES ($1, CAST($2 AS NUMERIC), $3, NULL, NULL, NULL, $4) RETURNING id",
    )
    .bind(topup_id)
    .bind(amount)
    .bind(status)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn set_history(
    db: &sqlx::PgPool,
    id: i64,
    status: &str,
    vtu_reference: Option<&str>,
    vtu_response_json: Option<&str>,
    error_message: Option<&str>,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE autotopup_autotopuphistory SET status = $1, vtu_reference = COALESCE($2, vtu_reference),
         vtu_response = COALESCE($3, vtu_response), error_message = COALESCE($4, error_message) WHERE id = $5",
    )
    .bind(status)
    .bind(vtu_reference)
    .bind(vtu_response_json)
    .bind(error_message)
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn history_for(
    db: &sqlx::PgPool,
    topup_id: i64,
    user_id: i64,
) -> Result<Vec<AutoTopUpHistoryRow>, sqlx::Error> {
    sqlx::query_as::<_, AutoTopUpHistoryRow>(
        "SELECT h.id, CAST(h.amount AS TEXT) AS amount, h.status, h.vtu_reference, h.vtu_response,
                h.error_message, h.executed_at, h.auto_topup_id
         FROM autotopup_autotopuphistory h
         JOIN autotopup_autotopup t ON t.id = h.auto_topup_id
         WHERE h.auto_topup_id = $1 AND t.user_id = $2
         ORDER BY h.executed_at DESC",
    )
    .bind(topup_id)
    .bind(user_id)
    .fetch_all(db)
    .await
}
