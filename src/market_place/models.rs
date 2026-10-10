//! Marketplace rows. Mirrors `market_place/models.py`.
//!
//! UUID primary keys are real `uuid` columns (Django `UUIDField`).
//! Responses render them dashed (`str(uuid)`), and incoming ids are
//! accepted dashed or plain. Money columns are decimal text; math goes
//! through the wallet crate's cent helpers.

use sqlx::FromRow;

/// New random id, dashed lowercase like Django's `str(UUIDField)`.
///
/// Postgres `uuid` columns only accept the dashed spelling, so ids are
/// created (and normalized) dashed end to end.
pub fn new_id() -> String {
    uuid::Uuid::new_v4().hyphenated().to_string()
}

/// NOTE: decimal columns are always `CAST(x AS TEXT)` — Postgres has no
/// implicit NUMERIC-to-text decode into String (Django converts transparently).
pub const TICKET_TYPE_COLS: &str = "CAST(id AS TEXT) AS id, name, CAST(price AS TEXT) AS price, quantity_available, created_at, CAST(event_id AS TEXT) AS event_id, description, initial_quantity";

pub const ISSUED_TICKET_COLS: &str = "CAST(id AS TEXT) AS id, owner_name, owner_email, qr_code, status, created_at, CAST(event_id AS TEXT) AS event_id, purchased_by_id, canceled_at, cancellation_reason, qr_code_image, CAST(refund_amount AS TEXT) AS refund_amount, scanned_at, scanned_by_id, transfer_count, transferred_at, transferred_to, updated_at, CAST(ticket_type_id AS TEXT) AS ticket_type_id";

pub const EVENTINFO_COLS: &str = "CAST(id AS TEXT) AS id, event_title, hosted_by, category, event_banner, ticket_image, event_date, event_location, event_description, is_free, is_approved, created_at, CAST(vendor_id AS TEXT) AS vendor_id, quantity, event_mode, meeting_link, cancel_failed, cancel_processed, cancel_refunded, cancel_status, cancel_total, canceled_at, canceled_by_id, cancellation_reason, is_canceled";

pub const VENDOR_COLS: &str = "CAST(id AS TEXT) AS id, phone_number, email, brand_name, residential_address, state, city, is_verified, created_at, rejection_reason, business_description, business_type, categories, event_authorization, id_document, id_type, monthly_volume, proof_of_address, legal_full_name, user_id, updated_at, verification_status";

pub const SCANNER_COLS: &str = "CAST(id AS TEXT) AS id, created_at, CAST(event_id AS TEXT) AS event_id, user_id";

pub const WITHDRAWAL_COLS: &str = "CAST(id AS TEXT) AS id, CAST(amount AS TEXT) AS amount, status, payment_reference, created_at, completed_at, CAST(event_id AS TEXT) AS event_id, CAST(amount_credited AS TEXT) AS amount_credited, CAST(platform_fee AS TEXT) AS platform_fee";

/// Normalize an incoming id (dashed or plain) to dashed-lowercase canonical
/// form, like Django's `str(uuid)`. Used for every DB bind and comparison.
pub fn norm_id(raw: &str) -> Option<String> {
    uuid::Uuid::parse_str(raw.trim())
        .ok()
        .map(|u| u.hyphenated().to_string())
}

/// Render stored hex dashed, like `str(event.id)`.
pub fn dashed(hex: &str) -> String {
    uuid::Uuid::parse_str(hex)
        .map(|u| u.hyphenated().to_string())
        .unwrap_or_else(|_| hex.to_string())
}

/// Raw stored naive datetime (UTC) truncated to seconds, matching Django's
/// `strftime("%Y-%m-%d %H:%M:%S")` on aware values read back from the DB.
pub fn utc_wall(raw: &str) -> String {
    raw.chars().take(19).collect()
}

/// `str()` of an aware UTC datetime read from the DB (`+00:00` suffix).
pub fn utc_str(raw: &str) -> String {
    format!("{}+00:00", utc_wall(raw))
}

#[derive(Debug, Clone, FromRow)]
pub struct TicketVendor {
    pub id: String,
    pub phone_number: Option<String>,
    pub email: Option<String>,
    pub brand_name: Option<String>,
    pub residential_address: Option<String>,
    pub state: Option<String>,
    pub city: Option<String>,
    pub is_verified: bool,
    pub created_at: crate::time::NaiveUtc,
    pub rejection_reason: Option<String>,
    pub business_description: Option<String>,
    pub business_type: Option<String>,
    pub categories: Option<String>,
    pub event_authorization: Option<String>,
    pub id_document: Option<String>,
    pub id_type: Option<String>,
    pub monthly_volume: Option<String>,
    pub proof_of_address: Option<String>,
    pub legal_full_name: Option<String>,
    pub user_id: Option<i64>,
    pub updated_at: crate::time::NaiveUtc,
    pub verification_status: Option<String>,
}

#[derive(Debug, Clone, FromRow)]
pub struct EventInfo {
    pub id: String,
    pub event_title: String,
    pub hosted_by: String,
    pub category: String,
    pub event_banner: String,
    pub ticket_image: Option<String>,
    pub event_date: crate::time::NaiveUtc,
    pub event_location: Option<String>,
    pub event_description: Option<String>,
    pub is_free: bool,
    pub is_approved: bool,
    pub created_at: crate::time::NaiveUtc,
    pub vendor_id: String,
    pub quantity: Option<i32>,
    pub event_mode: String,
    pub meeting_link: Option<String>,
    pub cancel_failed: i32,
    pub cancel_processed: i32,
    pub cancel_refunded: i32,
    pub cancel_status: String,
    pub cancel_total: i32,
    pub canceled_at: Option<crate::time::NaiveUtc>,
    pub canceled_by_id: Option<i64>,
    pub cancellation_reason: Option<String>,
    pub is_canceled: bool,
}

#[derive(Debug, Clone, FromRow)]
pub struct TicketType {
    pub id: String,
    pub name: String,
    pub price: String,
    pub quantity_available: i32,
    pub created_at: crate::time::NaiveUtc,
    pub event_id: String,
    pub description: Option<String>,
    pub initial_quantity: i32,
}

#[derive(Debug, Clone, FromRow)]
pub struct IssuedTicket {
    pub id: String,
    pub owner_name: String,
    pub owner_email: String,
    pub qr_code: String,
    pub status: String,
    pub created_at: crate::time::NaiveUtc,
    pub event_id: String,
    pub purchased_by_id: Option<i64>,
    pub canceled_at: Option<crate::time::NaiveUtc>,
    pub cancellation_reason: Option<String>,
    pub qr_code_image: Option<String>,
    pub refund_amount: Option<String>,
    pub scanned_at: Option<crate::time::NaiveUtc>,
    pub scanned_by_id: Option<i64>,
    pub transfer_count: i32,
    pub transferred_at: Option<crate::time::NaiveUtc>,
    pub transferred_to: Option<String>,
    pub updated_at: crate::time::NaiveUtc,
    pub ticket_type_id: Option<String>,
}

#[derive(Debug, Clone, FromRow)]
pub struct EventScanner {
    pub id: String,
    pub created_at: crate::time::NaiveUtc,
    pub event_id: String,
    pub user_id: i64,
}

#[derive(Debug, Clone, FromRow)]
pub struct EventWithdrawal {
    pub id: String,
    pub amount: String,
    pub status: String,
    pub payment_reference: Option<String>,
    pub created_at: crate::time::NaiveUtc,
    pub completed_at: Option<crate::time::NaiveUtc>,
    pub event_id: String,
    pub amount_credited: String,
    pub platform_fee: String,
}

pub async fn vendor_for_user(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<TicketVendor>, sqlx::Error> {
    sqlx::query_as::<_, TicketVendor>(&format!("SELECT {} FROM market_place_ticketvendor WHERE user_id = $1", VENDOR_COLS))
        .bind(user_id)
        .fetch_optional(db)
        .await
}

pub async fn vendor_by_id(
    db: &sqlx::PgPool,
    id_hex: &str,
) -> Result<Option<TicketVendor>, sqlx::Error> {
    sqlx::query_as::<_, TicketVendor>(&format!("SELECT {} FROM market_place_ticketvendor WHERE id = CAST($1 AS UUID)", VENDOR_COLS))
        .bind(id_hex)
        .fetch_optional(db)
        .await
}

pub async fn event_by_id(
    db: &sqlx::PgPool,
    id_hex: &str,
) -> Result<Option<EventInfo>, sqlx::Error> {
    sqlx::query_as::<_, EventInfo>(&format!("SELECT {} FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)", EVENTINFO_COLS))
        .bind(id_hex)
        .fetch_optional(db)
        .await
}

pub async fn raw_event_date(
    db: &sqlx::PgPool,
    id_hex: &str,
) -> Result<Option<String>, sqlx::Error> {
    let row: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(event_date AS TEXT) FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)",
    )
    .bind(id_hex)
    .fetch_optional(db)
    .await?;
    Ok(row.map(|r| r.0))
}

pub async fn ticket_types_for(
    db: &sqlx::PgPool,
    event_hex: &str,
) -> Result<Vec<TicketType>, sqlx::Error> {
    sqlx::query_as::<_, TicketType>(
        &format!("SELECT {} FROM market_place_tickettype WHERE event_id = CAST($1 AS UUID) ORDER BY market_place_tickettype.price ASC", TICKET_TYPE_COLS),
    )
    .bind(event_hex)
    .fetch_all(db)
    .await
}

pub async fn ticket_type_by_name(
    db: &sqlx::PgPool,
    event_hex: &str,
    name: &str,
) -> Result<Option<TicketType>, sqlx::Error> {
    sqlx::query_as::<_, TicketType>(
        &format!("SELECT {} FROM market_place_tickettype WHERE event_id = CAST($1 AS UUID) AND LOWER(name) = LOWER($2)", TICKET_TYPE_COLS),
    )
    .bind(event_hex)
    .bind(name)
    .fetch_optional(db)
    .await
}

pub async fn issued_count(
    db: &sqlx::PgPool,
    event_hex: &str,
    exclude_canceled: bool,
) -> Result<i32, sqlx::Error> {
    let sql = if exclude_canceled {
        "SELECT COUNT(*) FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID) AND status != 'canceled'"
    } else {
        "SELECT COUNT(*) FROM market_place_issuedticket WHERE event_id = CAST($1 AS UUID)"
    };
    let row: (i64,) = sqlx::query_as(sql).bind(event_hex).fetch_one(db).await?;
    Ok(row.0.try_into().unwrap_or(i32::MAX))
}

pub async fn ticket_by_id(
    db: &sqlx::PgPool,
    id_hex: &str,
) -> Result<Option<IssuedTicket>, sqlx::Error> {
    sqlx::query_as::<_, IssuedTicket>(&format!("SELECT {} FROM market_place_issuedticket WHERE id = CAST($1 AS UUID)", ISSUED_TICKET_COLS))
        .bind(id_hex)
        .fetch_optional(db)
        .await
}

pub async fn profile_email(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<String>, sqlx::Error> {
    let row: Option<(String,)> =
        sqlx::query_as("SELECT email FROM accounts_profile WHERE id = $1")
            .bind(user_id)
            .fetch_optional(db)
            .await?;
    Ok(row.map(|r| r.0))
}

/// Direct balance top-up with no ledger entry, mirroring Django's
/// `wallet.balance += refund_amount; wallet.save()` in `CancelTicketView`.
pub async fn raw_credit_balance(
    db: &sqlx::PgPool,
    user_id: i64,
    amount_cents: i64,
) -> Result<String, sqlx::Error> {
    let row: Option<(String,)> =
        sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = $1")
            .bind(user_id)
            .fetch_optional(db)
            .await?;
    let current = row
        .as_ref()
        .and_then(|r| crate::wallet::models::parse_cents(&r.0).ok())
        .unwrap_or(0);
    let next = crate::wallet::models::cents_to_decimal(current + amount_cents);
    sqlx::query("UPDATE wallet_wallet SET balance = $1, updated_at = $2 WHERE user_id = $3")
        .bind(&next)
        .bind(crate::time::now_str())
        .bind(user_id)
        .execute(db)
        .await?;
    Ok(next)
}

pub async fn wallet_balance_cents(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Result<Option<i64>, sqlx::Error> {
    let row: Option<(String,)> =
        sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = $1")
            .bind(user_id)
            .fetch_optional(db)
            .await?;
    Ok(row.and_then(|r| crate::wallet::models::parse_cents(&r.0).ok()))
}
