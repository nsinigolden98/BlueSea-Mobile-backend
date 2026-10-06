//! Wallet ledger logic. Mirrors `wallet/models.py`:
//! `Wallet` row, atomic `credit()`/`debit()` with idempotent `reference`,
//! `WalletTransaction` rows, and Channels-style balance pushes
//! (delivered here through the in-process `WalletHub`).

use sqlx::FromRow;
use uuid::Uuid;

use rust_decimal::Decimal;
use rust_decimal::RoundingStrategy;

use crate::transactions::models as ledger;

#[derive(Debug, Clone, FromRow)]
pub struct Wallet {
    pub id: i64,
    pub balance: String,
    pub locked_balance: String,
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
    pub is_active: bool,
    pub user_id: i64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum WalletError {
    InvalidAmount,
    InsufficientFunds,
    WalletNotFound,
    Db(String),
}

impl From<sqlx::Error> for WalletError {
    fn from(e: sqlx::Error) -> Self {
        WalletError::Db(e.to_string())
    }
}

/// Snapshot returned after a credit/debit (raw + formatted, like the
/// Channels `wallet_update` event payload).
#[derive(Debug, Clone)]
pub struct WalletBalances {
    pub balance: String,
    pub balance_formatted: String,
    pub locked_balance: String,
    pub locked_balance_formatted: String,
    pub available_balance: String,
    pub available_balance_formatted: String,
}

impl WalletBalances {
    pub fn from_cents(balance_cents: i64, locked_cents: i64) -> Self {
        Self {
            balance: cents_to_decimal(balance_cents),
            balance_formatted: format_naira(balance_cents),
            locked_balance: cents_to_decimal(locked_cents),
            locked_balance_formatted: format_naira(locked_cents),
            // available_balance == balance, like Django's property
            available_balance: cents_to_decimal(balance_cents),
            available_balance_formatted: format_naira(balance_cents),
        }
    }
}

// ---------- money helpers ----------
//
// Balances are stored under SQLite NUMERIC affinity, so reads come back as
// "59600", "59600.00" or "10.5" depending on what Django wrote. All math
// happens in integer cents; writes use canonical "W.cc" strings.

/// Parse a decimal money string into integer cents.
/// Rejects empty input, more than one `.`, and non-digit characters.
pub fn parse_cents(raw: &str) -> Result<i64, WalletError> {
    let s = raw.trim().trim_start_matches('+');
    if s.is_empty() {
        return Err(WalletError::InvalidAmount);
    }
    let (neg, s) = match s.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, s),
    };
    if s.is_empty() {
        return Err(WalletError::InvalidAmount);
    }
    let mut parts = s.split('.');
    let whole = parts.next().unwrap_or("");
    let frac = parts.next().unwrap_or("");
    if parts.next().is_some() || whole.is_empty() && frac.is_empty() {
        return Err(WalletError::InvalidAmount);
    }
    if !whole.chars().all(|c| c.is_ascii_digit()) || !frac.chars().all(|c| c.is_ascii_digit()) {
        return Err(WalletError::InvalidAmount);
    }
    if frac.len() > 2 {
        return Err(WalletError::InvalidAmount);
    }
    let whole_cents: i64 = if whole.is_empty() {
        0
    } else {
        whole
            .parse()
            .map_err(|_| WalletError::InvalidAmount)?
    };
    let frac_cents: i64 = match frac.len() {
        0 => 0,
        1 => frac.parse::<i64>().map_err(|_| WalletError::InvalidAmount)? * 10,
        _ => frac.parse().map_err(|_| WalletError::InvalidAmount)?,
    };
    let total = whole_cents
        .checked_mul(100)
        .and_then(|v| v.checked_add(frac_cents))
        .ok_or(WalletError::InvalidAmount)?;
    Ok(if neg { -total } else { total })
}

/// Canonical decimal string for storage, e.g. 5960000 -> "59600.00".
pub fn cents_to_decimal(cents: i64) -> String {
    let (sign, abs) = if cents < 0 { ("-", cents.unsigned_abs()) } else { ("", cents as u64) };
    format!("{sign}{}.{:02}", abs / 100, abs % 100)
}

/// DRF `DecimalField(max_digits=12, decimal_places=2)` output shape:
/// half-even to 2dp, always shown (e.g. "0" -> "0.00").
pub fn dec2(raw: &str) -> String {
    use rust_decimal::RoundingStrategy;
    raw.trim()
        .parse::<rust_decimal::Decimal>()
        .map(|d| {
            let mut q =
                d.round_dp_with_strategy(2, RoundingStrategy::MidpointNearestEven);
            q.rescale(2);
            q.to_string()
        })
        .unwrap_or_else(|_| raw.to_string())
}

/// Naira display string, e.g. 5960000 -> "₦59,600.00".
pub fn format_naira(cents: i64) -> String {
    let (sign, abs) = if cents < 0 { ("-", cents.unsigned_abs()) } else { ("", cents as u64) };
    let digits = format!("{}", abs / 100);
    let grouped: String = digits
        .chars()
        .rev()
        .enumerate()
        .flat_map(|(i, c)| {
            if i > 0 && i % 3 == 0 {
                vec![',', c]
            } else {
                vec![c]
            }
        })
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect();
    format!("{sign}₦{grouped}.{:02}", abs % 100)
}

pub async fn get_by_user(
    db: &sqlx::SqlitePool,
    user_id: i64,
) -> Result<Option<Wallet>, sqlx::Error> {
    sqlx::query_as::<_, Wallet>(
        "SELECT id, CAST(balance AS TEXT) AS balance, CAST(locked_balance AS TEXT) AS locked_balance, created_at, updated_at, is_active, user_id
         FROM wallet_wallet WHERE user_id = ?",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await
}

/// Atomic credit with idempotent `reference`.
/// Mirrors `Wallet.credit()`: positive amounts only, duplicate references are
/// no-ops, a `CREDIT` ledger row is written, then a balance push is emitted.
///
/// NOTE: Django uses `select_for_update()` (a no-op on SQLite, honoured on
/// Postgres). This port runs the read-modify-write in one transaction, which
/// matches Django-on-SQLite semantics exactly; add `FOR UPDATE` when the
/// production pool moves to Postgres.
pub async fn credit(
    db: &sqlx::SqlitePool,
    hub: &super::hub::WalletHub,
    wallet_id: i64,
    user_id: i64,
    amount: &str,
    description: &str,
    reference: Option<&str>,
) -> Result<WalletBalances, WalletError> {
    let amount_cents = parse_cents(amount)?;
    if amount_cents <= 0 {
        return Err(WalletError::InvalidAmount);
    }
    let reference = reference
        .map(|r| r.to_string())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    let mut tx = db.begin().await?;
    if ledger::reference_exists_tx(&mut tx, &reference).await? {
        tx.commit().await?;
        return current_balances(db, wallet_id).await;
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = ?",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let new_balance = parse_cents(&balance_raw)? + amount_cents;
    let locked_cents = parse_cents(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = ?, updated_at = ? WHERE id = ?")
        .bind(cents_to_decimal(new_balance))
        .bind(&now)
        .bind(wallet_id)
        .execute(&mut *tx)
        .await?;
    ledger::record_tx(
        &mut tx,
        wallet_id,
        amount_cents,
        "CREDIT",
        description,
        &reference,
        &now,
    )
    .await?;
    tx.commit().await?;

    let balances = WalletBalances::from_cents(new_balance, locked_cents);
    hub.publish_update(
        user_id,
        &balances,
        &cents_to_decimal(amount_cents),
        &reference,
        description,
        "CREDIT",
    );
    Ok(balances)
}

/// Atomic debit. Mirrors `Wallet.debit()`: raises `InsufficientFunds` when
/// the balance is short, duplicate references are no-ops.
pub async fn debit(
    db: &sqlx::SqlitePool,
    hub: &super::hub::WalletHub,
    wallet_id: i64,
    user_id: i64,
    amount: &str,
    description: &str,
    reference: Option<&str>,
) -> Result<WalletBalances, WalletError> {
    let amount_cents = parse_cents(amount)?;
    if amount_cents <= 0 {
        return Err(WalletError::InvalidAmount);
    }
    let reference = reference
        .map(|r| r.to_string())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    let mut tx = db.begin().await?;
    if ledger::reference_exists_tx(&mut tx, &reference).await? {
        tx.commit().await?;
        return current_balances(db, wallet_id).await;
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = ?",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let balance_cents = parse_cents(&balance_raw)?;
    if balance_cents < amount_cents {
        return Err(WalletError::InsufficientFunds);
    }
    let new_balance = balance_cents - amount_cents;
    let locked_cents = parse_cents(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = ?, updated_at = ? WHERE id = ?")
        .bind(cents_to_decimal(new_balance))
        .bind(&now)
        .bind(wallet_id)
        .execute(&mut *tx)
        .await?;
    ledger::record_tx(
        &mut tx,
        wallet_id,
        amount_cents,
        "DEBIT",
        description,
        &reference,
        &now,
    )
    .await?;
    tx.commit().await?;

    let balances = WalletBalances::from_cents(new_balance, locked_cents);
    hub.publish_update(
        user_id,
        &balances,
        &cents_to_decimal(amount_cents),
        &reference,
        description,
        "DEBIT",
    );
    Ok(balances)
}

/// Full-precision decimal balance snapshot (group-payment path).
fn balances_from_decimal(balance: Decimal, locked: Decimal) -> WalletBalances {
    WalletBalances {
        balance: balance.to_string(),
        balance_formatted: format_naira(decimal_cents(&balance)),
        locked_balance: locked.to_string(),
        locked_balance_formatted: format_naira(decimal_cents(&locked)),
        available_balance: balance.to_string(),
        available_balance_formatted: format_naira(decimal_cents(&balance)),
    }
}

/// Display cents for a Decimal (quantized half-even to 2dp, like Django's
/// `:,.2f` formatting of stored balances).
fn decimal_cents(d: &Decimal) -> i64 {
    let q = d.round_dp_with_strategy(2, RoundingStrategy::MidpointNearestEven);
    let scaled = (q * Decimal::new(100, 0)).round();
    scaled.to_string().parse::<i64>().unwrap_or(0)
}

fn parse_decimal(raw: &str) -> Result<Decimal, WalletError> {
    raw.trim()
        .parse::<Decimal>()
        .map_err(|_| WalletError::InvalidAmount)
}

/// Exact-decimal credit for group-payment shares (Django divides totals at
/// full decimal precision). Idempotent on `reference`, emits balance pushes.
pub async fn credit_decimal(
    db: &sqlx::SqlitePool,
    hub: &super::hub::WalletHub,
    wallet_id: i64,
    user_id: i64,
    amount: Decimal,
    description: &str,
    reference: &str,
) -> Result<WalletBalances, WalletError> {
    if amount <= Decimal::ZERO {
        return Err(WalletError::InvalidAmount);
    }
    let mut tx = db.begin().await?;
    if ledger::reference_exists_tx(&mut tx, reference).await? {
        tx.commit().await?;
        return current_balances(db, wallet_id).await;
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = ?",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let new_balance = parse_decimal(&balance_raw)? + amount;
    let locked = parse_decimal(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = ?, updated_at = ? WHERE id = ?")
        .bind(new_balance.to_string())
        .bind(&now)
        .bind(wallet_id)
        .execute(&mut *tx)
        .await?;
    ledger::record_tx_str(
        &mut tx,
        wallet_id,
        &amount.to_string(),
        "CREDIT",
        description,
        reference,
        &now,
    )
    .await?;
    tx.commit().await?;

    let balances = balances_from_decimal(new_balance, locked);
    hub.publish_update(
        user_id,
        &balances,
        &amount.to_string(),
        reference,
        description,
        "CREDIT",
    );
    Ok(balances)
}

/// Exact-decimal debit for group-payment shares. Mirrors `Wallet.debit()`.
pub async fn debit_decimal(
    db: &sqlx::SqlitePool,
    hub: &super::hub::WalletHub,
    wallet_id: i64,
    user_id: i64,
    amount: Decimal,
    description: &str,
    reference: &str,
) -> Result<WalletBalances, WalletError> {
    if amount <= Decimal::ZERO {
        return Err(WalletError::InvalidAmount);
    }
    let mut tx = db.begin().await?;
    if ledger::reference_exists_tx(&mut tx, reference).await? {
        tx.commit().await?;
        return current_balances(db, wallet_id).await;
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = ?",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let balance = parse_decimal(&balance_raw)?;
    if balance < amount {
        return Err(WalletError::InsufficientFunds);
    }
    let new_balance = balance - amount;
    let locked = parse_decimal(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = ?, updated_at = ? WHERE id = ?")
        .bind(new_balance.to_string())
        .bind(&now)
        .bind(wallet_id)
        .execute(&mut *tx)
        .await?;
    ledger::record_tx_str(
        &mut tx,
        wallet_id,
        &amount.to_string(),
        "DEBIT",
        description,
        reference,
        &now,
    )
    .await?;
    tx.commit().await?;

    let balances = balances_from_decimal(new_balance, locked);
    hub.publish_update(
        user_id,
        &balances,
        &amount.to_string(),
        reference,
        description,
        "DEBIT",
    );
    Ok(balances)
}

async fn current_balances(
    db: &sqlx::SqlitePool,
    wallet_id: i64,
) -> Result<WalletBalances, WalletError> {    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = ?",
    )
    .bind(wallet_id)
    .fetch_optional(db)
    .await?;
    match row {
        Some((b, l)) => Ok(WalletBalances::from_cents(parse_cents(&b)?, parse_cents(&l)?)),
        None => Err(WalletError::WalletNotFound),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::wallet::hub::WalletHub;

    #[test]
    fn parse_amounts() {
        assert_eq!(parse_cents("59600").unwrap(), 5_960_000);
        assert_eq!(parse_cents("59600.00").unwrap(), 5_960_000);
        assert_eq!(parse_cents("10.5").unwrap(), 1050);
        assert_eq!(parse_cents("0.01").unwrap(), 1);
        assert_eq!(parse_cents(" 100 ").unwrap(), 10_000);
        assert!(parse_cents("").is_err());
        assert!(parse_cents("abc").is_err());
        assert!(parse_cents("1.234").is_err());
        assert!(parse_cents("1.2.3").is_err());
    }

    #[test]
    fn naira_formatting_matches_django() {
        // Django: f"₦{Decimal('59600'):,.2f}" == "₦59,600.00"
        assert_eq!(format_naira(5_960_000), "₦59,600.00");
        assert_eq!(format_naira(0), "₦0.00");
        assert_eq!(format_naira(50), "₦0.50");
        assert_eq!(format_naira(1_000_000_00), "₦1,000,000.00");
        assert_eq!(cents_to_decimal(5_960_000), "59600.00");
    }

    async fn memory_db() -> sqlx::SqlitePool {
        let pool = sqlx::SqlitePool::connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::query(
            "CREATE TABLE wallet_wallet (id INTEGER PRIMARY KEY AUTOINCREMENT, balance decimal NOT NULL,
             locked_balance decimal NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL,
             is_active bool NOT NULL, user_id bigint NOT NULL UNIQUE)",
        )
        .execute(&pool)
        .await
        .unwrap();
        sqlx::query(
            "CREATE TABLE transactions_wallettransaction (id INTEGER PRIMARY KEY AUTOINCREMENT, amount decimal NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at datetime NOT NULL, wallet_id bigint NOT NULL)",
        )
        .execute(&pool)
        .await
        .unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (5000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1, 1)",
        )
        .execute(&pool)
        .await
        .unwrap();
        pool
    }

    #[tokio::test]
    async fn credit_debit_idempotency_and_overdraft() {
        let db = memory_db().await;
        let hub = WalletHub::default();

        let b = credit(&db, &hub, 1, 1, "1000", "Test credit", Some("ref-1"))
            .await
            .unwrap();
        assert_eq!(b.balance, "6000.00");

        // duplicate reference: no-op, balance unchanged
        let b2 = credit(&db, &hub, 1, 1, "1000", "Test credit", Some("ref-1"))
            .await
            .unwrap();
        assert_eq!(b2.balance, "6000.00");
        let n: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM transactions_wallettransaction WHERE reference = 'ref-1'",
        )
        .fetch_one(&db)
        .await
        .unwrap();
        assert_eq!(n.0, 1);

        let b3 = debit(&db, &hub, 1, 1, "500.50", "Test debit", Some("ref-2"))
            .await
            .unwrap();
        assert_eq!(b3.balance, "5499.50");
        assert_eq!(b3.balance_formatted, "₦5,499.50");

        assert!(matches!(
            debit(&db, &hub, 1, 1, "99999", "Too much", Some("ref-3")).await,
            Err(WalletError::InsufficientFunds)
        ));
        assert!(matches!(
            credit(&db, &hub, 1, 1, "0", "Zero", None).await,
            Err(WalletError::InvalidAmount)
        ));
        assert!(matches!(
            credit(&db, &hub, 1, 1, "-5", "Neg", None).await,
            Err(WalletError::InvalidAmount)
        ));
    }
}

#[cfg(test)]
mod dec2_tests {
    use super::dec2;
    #[test]
    fn dec2_shapes() {
        assert_eq!(dec2("0"), "0.00");
        assert_eq!(dec2("35"), "35.00");
        assert_eq!(dec2("333.333333"), "333.33");
        assert_eq!(dec2("10.005"), "10.00");
    }
}
