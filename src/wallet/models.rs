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
    pub total_in: String,
    pub total_out: String,
    pub created_at: crate::time::NaiveUtc,
    pub updated_at: crate::time::NaiveUtc,
    pub is_active: bool,
    pub user_id: i64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum WalletError {
    InvalidAmount,
    InsufficientFunds,
    WalletNotFound,
    /// Account frozen by tier-limit breach (admin unfreeze only).
    Frozen,
    /// Cumulative tier cap would be exceeded (limit in kobo).
    LimitExceeded { limit_cents: i64 },
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
// Balances are NUMERIC; reads come back as
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
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<Wallet>, sqlx::Error> {
    sqlx::query_as::<_, Wallet>(
        "SELECT id, CAST(balance AS TEXT) AS balance, CAST(locked_balance AS TEXT) AS locked_balance,
                CAST(total_in AS TEXT) AS total_in, CAST(total_out AS TEXT) AS total_out,
                created_at, updated_at, is_active, user_id
         FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await
}

/// Atomic credit with idempotent `reference`.
/// Mirrors `Wallet.credit()`: positive amounts only, duplicate references are
/// no-ops, a `CREDIT` ledger row is written, then a balance push is emitted.
///
/// NOTE: Django uses `select_for_update()`; this port runs the
/// read-modify-write in one transaction without row locking.
pub async fn credit(
    db: &sqlx::PgPool,
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
    let snap = tier_snap(&mut tx, user_id).await?;
    if snap.frozen {
        return Err(WalletError::Frozen);
    }
    let row: Option<(String, String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT), CAST(total_in AS TEXT) FROM wallet_wallet WHERE id = $1",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw, total_in_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let total_in_cents = parse_cents(&total_in_raw)?;
    if let Some(limit) = snap.limit_cents {
        if total_in_cents + amount_cents > limit {
            return Err(WalletError::LimitExceeded { limit_cents: limit });
        }
    }
    let new_balance = parse_cents(&balance_raw)? + amount_cents;
    let locked_cents = parse_cents(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), total_in = total_in + CAST($2 AS NUMERIC), updated_at = $3 WHERE id = $4")
        .bind(cents_to_decimal(new_balance))
        .bind(cents_to_decimal(amount_cents))
        .bind(crate::time::Ts(&now))
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
    db: &sqlx::PgPool,
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
    let snap = tier_snap(&mut tx, user_id).await?;
    if snap.frozen {
        return Err(WalletError::Frozen);
    }
    let row: Option<(String, String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT), CAST(total_out AS TEXT) FROM wallet_wallet WHERE id = $1",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw, total_out_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let balance_cents = parse_cents(&balance_raw)?;
    if balance_cents < amount_cents {
        return Err(WalletError::InsufficientFunds);
    }
    if let Some(limit) = snap.limit_cents {
        if parse_cents(&total_out_raw)? + amount_cents > limit {
            return Err(WalletError::LimitExceeded { limit_cents: limit });
        }
    }
    let new_balance = balance_cents - amount_cents;
    let locked_cents = parse_cents(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), total_out = total_out + CAST($2 AS NUMERIC), updated_at = $3 WHERE id = $4")
        .bind(cents_to_decimal(new_balance))
        .bind(cents_to_decimal(amount_cents))
        .bind(crate::time::Ts(&now))
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
    db: &sqlx::PgPool,
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
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = $1",
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
    sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), updated_at = $2 WHERE id = $3")
        .bind(new_balance.to_string())
        .bind(crate::time::Ts(&now))
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
    db: &sqlx::PgPool,
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
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = $1",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let snap = tier_snap(&mut tx, user_id).await?;
    if snap.frozen {
        return Err(WalletError::Frozen);
    }
    let balance = parse_decimal(&balance_raw)?;
    if balance < amount {
        return Err(WalletError::InsufficientFunds);
    }
    let total_out: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(total_out AS TEXT) FROM wallet_wallet WHERE id = $1",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    if let Some(limit) = snap.limit_cents {
        let spent = total_out.map(|(t,)| parse_cents(&t)).transpose()?.unwrap_or(0);
        let amount_cents = decimal_cents(&amount);
        if spent + amount_cents > limit {
            return Err(WalletError::LimitExceeded { limit_cents: limit });
        }
    }
    let new_balance = balance - amount;
    let locked = parse_decimal(&locked_raw)?;
    let now = crate::time::now_str();
    sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), total_out = total_out + CAST($2 AS NUMERIC), updated_at = $3 WHERE id = $4")
        .bind(new_balance.to_string())
        .bind(amount.to_string())
        .bind(crate::time::Ts(&now))
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

/// Tier/frozen snapshot for limit enforcement, read inside the
/// caller's transaction so check and movement are atomic.
struct TierSnap {
    frozen: bool,
    limit_cents: Option<i64>,
}

async fn tier_snap(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    user_id: i64,
) -> Result<TierSnap, WalletError> {
    let row: Option<(Option<String>, Option<String>, Option<String>, Option<String>, Option<String>, bool)> =
        sqlx::query_as(
            "SELECT phone, nin_encrypted, bvn_encrypted, house_address, utility_bill_image, is_frozen
             FROM accounts_profile WHERE id = $1",
        )
        .bind(user_id)
        .fetch_optional(&mut **tx)
        .await?;
    let Some((phone, nin, bvn, addr, bill, frozen)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let has = |v: &Option<String>| v.as_deref().map(|s| !s.trim().is_empty()).unwrap_or(false);
    let tier: u8 = if !has(&phone) {
        0
    } else if !has(&nin) {
        1
    } else if !has(&bvn) {
        2
    } else if !(has(&addr) && has(&bill)) {
        3
    } else {
        4
    };
    let limit_cents = match tier {
        0 | 1 => Some(crate::accounts::tier::T0_T1_LIMIT_CENTS),
        2 => Some(crate::accounts::tier::T2_LIMIT_CENTS),
        3 => Some(crate::accounts::tier::T3_LIMIT_CENTS),
        _ => None,
    };
    Ok(TierSnap { frozen, limit_cents })
}

async fn current_balances(
    db: &sqlx::PgPool,
    wallet_id: i64,
) -> Result<WalletBalances, WalletError> {
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = $1",
    )
    .bind(wallet_id)
    .fetch_optional(db)
    .await?;
    match row {
        Some((b, l)) => Ok(WalletBalances::from_cents(parse_cents(&b)?, parse_cents(&l)?)),
        None => Err(WalletError::WalletNotFound),
    }
}

/// Atomically move `amount_cents` from `balance` to `locked_balance`.
///
/// Single conditional UPDATE: concurrent lockers serialize on the row and
/// only winners (affected row) proceed. Returns `Ok(true)` when locked,
/// `Ok(false)` when funds are short. Callers MUST `unlock_amount` on
/// gateway failure or `finalize_locked_debit` on success — never leave
/// funds locked.
/// Result of a failed lock attempt (distinguishes funds vs tier vs frozen).
async fn lock_failure_reason(
    db: &sqlx::PgPool,
    wallet_id: i64,
    user_id: i64,
    amount_cents: i64,
) -> WalletError {
    let row: Option<(String, String, bool)> = sqlx::query_as(
        "SELECT CAST(w.balance AS TEXT), CAST(w.total_out AS TEXT), p.is_frozen
         FROM wallet_wallet w JOIN accounts_profile p ON p.id = $2 WHERE w.id = $1",
    )
    .bind(wallet_id)
    .bind(user_id)
    .fetch_optional(db)
    .await
    .unwrap_or(None);
    let Some((balance_raw, total_out_raw, frozen)) = row else {
        return WalletError::WalletNotFound;
    };
    if frozen {
        return WalletError::Frozen;
    }
    let limit = {
        let r: Option<(Option<String>, Option<String>, Option<String>, Option<String>, Option<String>)> =
            sqlx::query_as(
                "SELECT phone, nin_encrypted, bvn_encrypted, house_address, utility_bill_image
                 FROM accounts_profile WHERE id = $1",
            )
            .bind(user_id)
            .fetch_optional(db)
            .await
            .unwrap_or(None);
        match r {
            Some((phone, nin, bvn, addr, bill)) => {
                let has =
                    |v: &Option<String>| v.as_deref().map(|s| !s.trim().is_empty()).unwrap_or(false);
                if !has(&phone) {
                    Some(crate::accounts::tier::T0_T1_LIMIT_CENTS)
                } else if !has(&nin) {
                    Some(crate::accounts::tier::T0_T1_LIMIT_CENTS)
                } else if !has(&bvn) {
                    Some(crate::accounts::tier::T2_LIMIT_CENTS)
                } else if !(has(&addr) && has(&bill)) {
                    Some(crate::accounts::tier::T3_LIMIT_CENTS)
                } else {
                    None
                }
            }
            None => None,
        }
    };
    if let Some(limit) = limit {
        let spent = parse_cents(&total_out_raw).unwrap_or(0);
        if spent + amount_cents > limit {
            return WalletError::LimitExceeded { limit_cents: limit };
        }
    }
    if parse_cents(&balance_raw).unwrap_or(0) < amount_cents {
        return WalletError::InsufficientFunds;
    }
    WalletError::Db("lock contention, retry".to_string())
}

pub async fn lock_amount(
    db: &sqlx::PgPool,
    wallet_id: i64,
    user_id: i64,
    amount_cents: i64,
    limit_cents: Option<i64>,
) -> Result<bool, WalletError> {
    if amount_cents <= 0 {
        return Err(WalletError::InvalidAmount);
    }
    let now = crate::time::now_str();
    // Atomic: balance, frozen flag, and cumulative out-cap in one predicate.
    let res = sqlx::query(
        "UPDATE wallet_wallet w
         SET balance = balance - CAST($1 AS NUMERIC),
             locked_balance = locked_balance + CAST($1 AS NUMERIC),
             updated_at = $2
         WHERE w.id = $3 AND w.balance >= CAST($1 AS NUMERIC)
           AND NOT (SELECT p.is_frozen FROM accounts_profile p WHERE p.id = $4)
           AND ($5 IS NULL OR w.total_out + CAST($1 AS NUMERIC) <= CAST($5 AS NUMERIC))",
    )
    .bind(cents_to_decimal(amount_cents))
    .bind(crate::time::Ts(&now))
    .bind(wallet_id)
    .bind(user_id)
    .bind(limit_cents)
    .execute(db)
    .await?;
    if res.rows_affected() == 1 {
        return Ok(true);
    }
    Err(lock_failure_reason(db, wallet_id, user_id, amount_cents).await)
}

/// Move previously locked funds back to `balance` (gateway failed).
/// Best-effort inverse of `lock_amount`; no-ops when the wallet is gone.
pub async fn unlock_amount(
    db: &sqlx::PgPool,
    wallet_id: i64,
    amount_cents: i64,
) -> Result<(), WalletError> {
    if amount_cents <= 0 {
        return Err(WalletError::InvalidAmount);
    }
    let now = crate::time::now_str();
    sqlx::query(
        "UPDATE wallet_wallet
         SET balance = balance + CAST($1 AS NUMERIC),
             locked_balance = locked_balance - CAST($1 AS NUMERIC),
             updated_at = $2
         WHERE id = $3",
    )
    .bind(cents_to_decimal(amount_cents))
    .bind(crate::time::Ts(&now))
    .bind(wallet_id)
    .execute(db)
    .await?;
    Ok(())
}

/// Settle locked funds after a successful gateway call: drop them from
/// `locked_balance`, record the DEBIT ledger row (idempotent on
/// `reference`), and publish the balance push. On DB failure the caller
/// should `unlock_amount` so funds don't stay locked.
pub async fn finalize_locked_debit(
    db: &sqlx::PgPool,
    hub: &super::hub::WalletHub,
    wallet_id: i64,
    user_id: i64,
    amount_cents: i64,
    description: &str,
    reference: &str,
) -> Result<WalletBalances, WalletError> {
    if amount_cents <= 0 {
        return Err(WalletError::InvalidAmount);
    }
    let mut tx = db.begin().await?;
    if ledger::reference_exists_tx(&mut tx, reference).await? {
        tx.commit().await?;
        return current_balances(db, wallet_id).await;
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = $1",
    )
    .bind(wallet_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some((balance_raw, locked_raw)) = row else {
        return Err(WalletError::WalletNotFound);
    };
    let locked_cents = parse_cents(&locked_raw)?;
    if locked_cents < amount_cents {
        return Err(WalletError::InsufficientFunds);
    }
    let now = crate::time::now_str();
    sqlx::query(
        "UPDATE wallet_wallet SET locked_balance = locked_balance - CAST($1 AS NUMERIC), total_out = total_out + CAST($1 AS NUMERIC), updated_at = $2 WHERE id = $3",
    )
    .bind(cents_to_decimal(amount_cents))
    .bind(crate::time::Ts(&now))
    .bind(wallet_id)
    .execute(&mut *tx)
    .await?;
    ledger::record_tx(&mut tx, wallet_id, amount_cents, "DEBIT", description, reference, &now).await?;
    tx.commit().await?;

    let balances = WalletBalances::from_cents(parse_cents(&balance_raw)?, locked_cents - amount_cents);
    hub.publish_update(user_id, &balances, &cents_to_decimal(amount_cents), reference, description, "DEBIT");
    Ok(balances)
}

/// Credit for externally-settled inflows (Nomba webhook: DVA/checkout money
/// already landed and cannot be refused). Bumps `total_in`; skips the
/// frozen/limit gates — the caller freezes the account when over cap.
pub async fn credit_external_inflow(
    db: &sqlx::PgPool,
    hub: &super::hub::WalletHub,
    wallet_id: i64,
    user_id: i64,
    amount: &str,
    description: &str,
    reference: &str,
) -> Result<WalletBalances, WalletError> {
    let amount_cents = parse_cents(amount)?;
    if amount_cents <= 0 {
        return Err(WalletError::InvalidAmount);
    }
    let mut tx = db.begin().await?;
    if ledger::reference_exists_tx(&mut tx, reference).await? {
        tx.commit().await?;
        return current_balances(db, wallet_id).await;
    }
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = $1",
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
    sqlx::query("UPDATE wallet_wallet SET balance = CAST($1 AS NUMERIC), total_in = total_in + CAST($2 AS NUMERIC), updated_at = $3 WHERE id = $4")
        .bind(cents_to_decimal(new_balance))
        .bind(cents_to_decimal(amount_cents))
        .bind(crate::time::Ts(&now))
        .bind(wallet_id)
        .execute(&mut *tx)
        .await?;
    ledger::record_tx(&mut tx, wallet_id, amount_cents, "CREDIT", description, reference, &now).await?;
    tx.commit().await?;
    let balances = WalletBalances::from_cents(new_balance, locked_cents);
    hub.publish_update(user_id, &balances, &cents_to_decimal(amount_cents), reference, description, "CREDIT");
    Ok(balances)
}

/// Lifetime tier counters + frozen flag for one user (funding pre-checks,
/// KYC status, post-inflow freeze decisions).
pub struct WalletTotals {
    pub wallet_id: i64,
    pub total_in_cents: i64,
    pub total_out_cents: i64,
    pub frozen: bool,
}

pub async fn wallet_totals(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<WalletTotals>, sqlx::Error> {
    let row: Option<(i64, String, String, bool)> = sqlx::query_as(
        "SELECT w.id, CAST(w.total_in AS TEXT), CAST(w.total_out AS TEXT), p.is_frozen
         FROM wallet_wallet w JOIN accounts_profile p ON p.id = w.user_id WHERE w.user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await?;
    Ok(row.map(|(wid, tin, tout, frozen)| WalletTotals {
        wallet_id: wid,
        total_in_cents: parse_cents(&tin).unwrap_or(0),
        total_out_cents: parse_cents(&tout).unwrap_or(0),
        frozen,
    }))
}

/// Freeze an account (tier-limit breach on external inflow). Unfreeze is
/// admin-only.
pub async fn freeze_account(db: &sqlx::PgPool, user_id: i64, reason: &str) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE accounts_profile SET is_frozen = TRUE, frozen_reason = $1 WHERE id = $2")
        .bind(reason)
        .bind(user_id)
        .execute(db)
        .await?;
    Ok(())
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

    async fn memory_db() -> sqlx::PgPool {
        let pool = crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, phone varchar(200) NULL,
             nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL,
             utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE)",
            "CREATE TABLE wallet_wallet (id BIGSERIAL PRIMARY KEY, balance NUMERIC NOT NULL,
             locked_balance NUMERIC NOT NULL, total_in NUMERIC NOT NULL DEFAULT 0, total_out NUMERIC NOT NULL DEFAULT 0,  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             is_active BOOLEAN NOT NULL, user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE transactions_wallettransaction (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL, wallet_id bigint NOT NULL)",
        ])
        .await;
        sqlx::query("INSERT INTO accounts_profile (phone, is_frozen) VALUES ('0801', FALSE)")
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (5000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', TRUE, 1)",
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

#[cfg(test)]
mod lock_tests {
    use super::*;
    use crate::wallet::hub::WalletHub;

    async fn lock_db() -> sqlx::PgPool {
        let pool = crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, phone varchar(200) NULL,
             nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL,
             utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE)",
            "CREATE TABLE wallet_wallet (id BIGSERIAL PRIMARY KEY, balance NUMERIC NOT NULL,
             locked_balance NUMERIC NOT NULL, total_in NUMERIC NOT NULL DEFAULT 0, total_out NUMERIC NOT NULL DEFAULT 0,
             created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             is_active BOOLEAN NOT NULL, user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE transactions_wallettransaction (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL, wallet_id bigint NOT NULL)",
        ])
        .await;
        sqlx::query(
            "INSERT INTO accounts_profile (phone, is_frozen) VALUES ('0801', FALSE)",
        )
        .execute(&pool)
        .await
        .unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, total_in, total_out, created_at, updated_at, is_active, user_id)
             VALUES (1000, 0, 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', TRUE, 1)",
        )
        .execute(&pool)
        .await
        .unwrap();
        pool
    }

    #[tokio::test]
    async fn concurrent_locks_single_winner() {
        // Balance covers exactly one of two concurrent full-balance locks:
        // the loser must see Ok(false), never a double lock.
        let db = lock_db().await;
        let (a, b) = tokio::join!(
            lock_amount(&db, 1, 1, 100_000, None),
            lock_amount(&db, 1, 1, 100_000, None),
        );
        // Winner Ok(true), loser Err(InsufficientFunds) — never a double lock.
        let results = [a, b];
        let wins = results.iter().filter(|r| matches!(r, Ok(true))).count();
        assert_eq!(wins, 1);
        assert!(results.iter().any(|r| matches!(r, Err(WalletError::InsufficientFunds))));
        let row: (String, String) = sqlx::query_as(
            "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = 1",
        )
        .fetch_one(&db)
        .await
        .unwrap();
        assert_eq!((row.0.as_str(), row.1.as_str()), ("0.00", "1000.00"));
    }

    #[tokio::test]
    async fn finalize_and_unlock_roundtrip() {
        let db = lock_db().await;
        let hub = WalletHub::default();
        assert!(lock_amount(&db, 1, 1, 40_000, None).await.unwrap());
        // Finalize settles from locked, keeps balance at 600.
        let b = finalize_locked_debit(&db, &hub, 1, 1, 40_000, "d", "lock-ref-1")
            .await
            .unwrap();
        assert_eq!((b.balance.as_str(), b.locked_balance.as_str()), ("600.00", "0.00"));
        // Same reference replays as a no-op.
        let b2 = finalize_locked_debit(&db, &hub, 1, 1, 40_000, "d", "lock-ref-1")
            .await
            .unwrap();
        assert_eq!(b2.balance.as_str(), "600.00");
        // Unlock path restores balance.
        assert!(lock_amount(&db, 1, 1, 10_000, None).await.unwrap());
        unlock_amount(&db, 1, 10_000).await.unwrap();
        let row: (String, String) = sqlx::query_as(
            "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE id = 1",
        )
        .fetch_one(&db)
        .await
        .unwrap();
        assert_eq!((row.0.as_str(), row.1.as_str()), ("600.00", "0.00"));
        // Short funds refuse without touching balances.
        assert!(matches!(
            lock_amount(&db, 1, 1, 70_000, None).await,
            Err(WalletError::InsufficientFunds)
        ));
        assert!(matches!(
            finalize_locked_debit(&db, &hub, 1, 1, 70_000, "d", "lock-ref-2").await,
            Err(WalletError::InsufficientFunds)
        ));
    }
}
