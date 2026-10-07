//! Affiliate engine. Mirrors `affiliate/utils.py`:
//! attribution (first wins), sale completion, payable sweep, wallet payout,
//! and revocation on ticket cancel.

use rust_decimal::Decimal;

use crate::payments::vtpass;
use crate::state::AppState;

use super::models as affiliate_models;

fn dec(raw: &str) -> Decimal {
    raw.parse::<Decimal>().unwrap_or(Decimal::ZERO)
}

pub async fn active_link(
    db: &sqlx::SqlitePool,
    affiliate_id: i64,
    event_id: &str,
) -> Result<Option<affiliate_models::AffiliateLinkRow>, sqlx::Error> {
    sqlx::query_as::<_, affiliate_models::AffiliateLinkRow>(
        "SELECT id, CAST(commission_rate AS TEXT) AS commission_rate, clicks, is_active, created_at, event_id, affiliate_id
         FROM affiliate_affiliatelink WHERE affiliate_id = ? AND event_id = ? AND is_active = 1",
    )
    .bind(affiliate_id)
    .bind(event_id)
    .fetch_optional(db)
    .await
}

pub async fn increment_clicks(db: &sqlx::SqlitePool, link_id: i64) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE affiliate_affiliatelink SET clicks = clicks + 1 WHERE id = ?")
        .bind(link_id)
        .execute(db)
        .await?;
    Ok(())
}

pub struct Attribution {
    pub sale_id: i64,
    pub status: String,
}

/// First-attribution-wins click recording. Returns None when invalid.
pub async fn record_attribution(
    db: &sqlx::SqlitePool,
    buyer_id: i64,
    event: &affiliate_models::EventView,
    affiliate_name: &str,
) -> Result<Option<Attribution>, sqlx::Error> {
    let affiliate = affiliate_models::profile_by_name(db, affiliate_name).await?;
    let Some(affiliate) = affiliate else {
        return Ok(None);
    };
    if affiliate.status != "approved" || affiliate.user_id == buyer_id || event.is_free {
        return Ok(None);
    }
    let link = active_link(db, affiliate.id, &event.id).await?;
    let Some(link) = link else {
        return Ok(None);
    };
    if let Some(existing) = sale_for_buyer(db, buyer_id, &event.id).await? {
        increment_clicks(db, link.id).await?;
        return Ok(Some(Attribution {
            sale_id: existing.0,
            status: existing.1,
        }));
    }
    let now = crate::time::now_str();
    let res = sqlx::query(
        "INSERT INTO affiliate_affiliatesale (ticket_count, gross_amount, commission_rate, commission_amount,
                status, created_at, payable_at, paid_at, revoked_at, affiliate_id, buyer_id, event_id,
                issued_ticket_id, link_id)
         VALUES (0, '0.00', ?, '0.00', 'pending', ?, NULL, NULL, NULL, ?, ?, ?, NULL, ?)",
    )
    .bind(&link.commission_rate)
    .bind(&now)
    .bind(affiliate.id)
    .bind(buyer_id)
    .bind(&event.id)
    .bind(link.id)
    .execute(db)
    .await?;
    increment_clicks(db, link.id).await?;
    Ok(Some(Attribution {
        sale_id: res.last_insert_rowid(),
        status: "pending".to_string(),
    }))
}

async fn sale_for_buyer(
    db: &sqlx::SqlitePool,
    buyer_id: i64,
    event_id: &str,
) -> Result<Option<(i64, String)>, sqlx::Error> {
    sqlx::query_as::<_, (i64, String)>(
        "SELECT id, status FROM affiliate_affiliatesale WHERE buyer_id = ? AND event_id = ? ORDER BY id LIMIT 1",
    )
    .bind(buyer_id)
    .bind(event_id)
    .fetch_optional(db)
    .await
}

/// Finalize a pending attribution on purchase (or record success directly).
/// Never blocks the purchase: invalid attributions return None.
/// `total` is the purchase gross in naira-cents; `first_ticket_hex` is the
/// dashless issued-ticket id (or None).
pub async fn complete_sale(
    db: &sqlx::SqlitePool,
    buyer_id: i64,
    event: &affiliate_models::EventView,
    affiliate_name: &str,
    first_ticket_hex: Option<&str>,
    quantity: i64,
    total_cents: i64,
) -> Result<Option<i64>, sqlx::Error> {
    let affiliate = affiliate_models::profile_by_name(db, affiliate_name).await?;
    let Some(affiliate) = affiliate else {
        return Ok(None);
    };
    if affiliate.status != "approved" || affiliate.user_id == buyer_id || event.is_free {
        return Ok(None);
    }
    if total_cents <= 0 {
        return Ok(None);
    }
    let link = active_link(db, affiliate.id, &event.id).await?;
    let Some(link) = link else {
        return Ok(None);
    };
    let total = Decimal::from(total_cents) / Decimal::from(100);
    let mut total = total;
    total.rescale(2);
    let rate = dec(&link.commission_rate);
    let mut commission = ((total * rate) / Decimal::from(100))
        .round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointNearestEven);
    commission.rescale(2);
    let now = crate::time::now_str();

    if let Some((sale_id, sale_status)) = sale_for_buyer(db, buyer_id, &event.id).await? {
        let owner: Option<(i64,)> = sqlx::query_as(
            "SELECT affiliate_id FROM affiliate_affiliatesale WHERE id = ?",
        )
        .bind(sale_id)
        .fetch_optional(db)
        .await?;
        if owner.map(|(a,)| a) != Some(affiliate.id) {
            return Ok(None);
        }
        if sale_status == "pending" {
            sqlx::query(
                "UPDATE affiliate_affiliatesale SET status = 'success', link_id = ?, issued_ticket_id = ?,
                 ticket_count = ?, gross_amount = ?, commission_rate = ?, commission_amount = ? WHERE id = ?",
            )
            .bind(link.id)
            .bind(first_ticket_hex)
            .bind(quantity)
            .bind(total.to_string())
            .bind(&link.commission_rate)
            .bind(commission.to_string())
            .bind(sale_id)
            .execute(db)
            .await?;
        }
        return Ok(Some(sale_id));
    }

    let res = sqlx::query(
        "INSERT INTO affiliate_affiliatesale (ticket_count, gross_amount, commission_rate, commission_amount,
                status, created_at, payable_at, paid_at, revoked_at, affiliate_id, buyer_id, event_id,
                issued_ticket_id, link_id)
         VALUES (?, ?, ?, ?, 'success', ?, NULL, NULL, NULL, ?, ?, ?, ?, ?)",
    )
    .bind(quantity)
    .bind(total.to_string())
    .bind(&link.commission_rate)
    .bind(commission.to_string())
    .bind(&now)
    .bind(affiliate.id)
    .bind(buyer_id)
    .bind(&event.id)
    .bind(first_ticket_hex)
    .bind(link.id)
    .execute(db)
    .await?;
    Ok(Some(res.last_insert_rowid()))
}

/// Mark past-event success sales payable. Returns the updated count.
pub async fn sweep_payable(
    db: &sqlx::SqlitePool,
    affiliate_id: Option<i64>,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let rows: Vec<(i64,)> = if let Some(aid) = affiliate_id {
        sqlx::query_as(
            "SELECT s.id FROM affiliate_affiliatesale s
             JOIN market_place_eventinfo e ON e.id = s.event_id
             WHERE s.status = 'success' AND e.event_date <= ? AND s.affiliate_id = ?",
        )
        .bind(now)
        .bind(aid)
        .fetch_all(db)
        .await?
    } else {
        sqlx::query_as(
            "SELECT s.id FROM affiliate_affiliatesale s
             JOIN market_place_eventinfo e ON e.id = s.event_id
             WHERE s.status = 'success' AND e.event_date <= ?",
        )
        .bind(now)
        .fetch_all(db)
        .await?
    };
    for (id,) in &rows {
        sqlx::query(
            "UPDATE affiliate_affiliatesale SET status = 'payable', payable_at = ? WHERE id = ?",
        )
        .bind(now)
        .bind(id)
        .execute(db)
        .await?;
    }
    Ok(rows.len() as i64)
}

/// Credit all payable commissions to the affiliate wallet.
/// Returns (paid sale ids, total display string, reference or None).
pub async fn pay_out(
    state: &AppState,
    affiliate_id: i64,
    user_id: i64,
) -> Result<(Vec<i64>, String, Option<String>), sqlx::Error> {
    let now = crate::time::now_str();
    sweep_payable(&state.db, Some(affiliate_id), &now).await?;
    let rows: Vec<(i64, String)> = sqlx::query_as(
        "SELECT id, CAST(commission_amount AS TEXT) FROM affiliate_affiliatesale
         WHERE affiliate_id = ? AND status = 'payable' ORDER BY id",
    )
    .bind(affiliate_id)
    .fetch_all(&state.db)
    .await?;
    if rows.is_empty() {
        return Ok((Vec::new(), "0.00".to_string(), None));
    }
    let mut total = rust_decimal::Decimal::new(0, 2);
    let mut paid = Vec::new();
    for (id, amount_raw) in &rows {
        sqlx::query(
            "UPDATE affiliate_affiliatesale SET status = 'paid', paid_at = ? WHERE id = ?",
        )
        .bind(&now)
        .bind(id)
        .execute(&state.db)
        .await?;
        total += dec(amount_raw);
        paid.push(*id);
    }
    let mut reference = None;
    if total > Decimal::ZERO {
        let wallet: Option<(i64,)> =
            sqlx::query_as("SELECT id FROM wallet_wallet WHERE user_id = ?")
                .bind(user_id)
                .fetch_optional(&state.db)
                .await?;
        if let Some((wallet_id,)) = wallet {
            reference = Some(format!("AFF-{}", vtpass::generate_reference_id()));
            let _ = crate::wallet::models::credit(
                &state.db,
                &state.wallet_hub,
                wallet_id,
                user_id,
                &total.to_string(),
                "Affiliate commission payout",
                reference.as_deref(),
            )
            .await;
        }
    }
    Ok((paid, crate::wallet::models::dec2(&total.to_string()), reference))
}

/// Revoke a success/payable sale whose ticket was canceled.
pub async fn revoke_sale(
    db: &sqlx::SqlitePool,
    issued_ticket_hex: &str,
    now: &str,
) -> Result<Option<i64>, sqlx::Error> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM affiliate_affiliatesale
         WHERE issued_ticket_id = ? AND status IN ('success', 'payable') ORDER BY id LIMIT 1",
    )
    .bind(issued_ticket_hex)
    .fetch_optional(db)
    .await?;
    if let Some((id,)) = row {
        sqlx::query(
            "UPDATE affiliate_affiliatesale SET status = 'revoked', revoked_at = ? WHERE id = ?",
        )
        .bind(now)
        .bind(id)
        .execute(db)
        .await?;
        return Ok(Some(id));
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;

    async fn memory_db() -> sqlx::SqlitePool {
        let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        for ddl in [
            "CREATE TABLE accounts_profile (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, password varchar(128) NOT NULL,
             last_login datetime NULL, is_superuser bool NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined datetime NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active bool NOT NULL,
             is_staff bool NOT NULL, is_admin bool NOT NULL, role varchar(200) NOT NULL, email_verified bool NOT NULL,
             created_on datetime NOT NULL, pin_is_set bool NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until datetime NULL, has_DVA bool NOT NULL)",
            "CREATE TABLE wallet_wallet (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, balance decimal NOT NULL,
             locked_balance decimal NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL,
             is_active bool NOT NULL, user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE transactions_wallettransaction (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, amount decimal NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at datetime NOT NULL, wallet_id bigint NOT NULL)",
            "CREATE TABLE market_place_ticketvendor (id char(32) NOT NULL PRIMARY KEY, is_verified bool NOT NULL,
             created_at datetime NOT NULL, updated_at datetime NOT NULL)",
            "CREATE TABLE market_place_eventinfo (id char(32) NOT NULL PRIMARY KEY, event_title varchar(255) NOT NULL,
             hosted_by varchar(255) NOT NULL, category varchar(50) NOT NULL, event_banner varchar(100) NOT NULL,
             event_date datetime NOT NULL, is_free bool NOT NULL, is_approved bool NOT NULL, created_at datetime NOT NULL,
             vendor_id char(32) NOT NULL, event_mode varchar(10) NOT NULL, cancel_failed integer NOT NULL,
             cancel_processed integer NOT NULL, cancel_refunded integer NOT NULL, cancel_status varchar(30) NOT NULL,
             cancel_total integer NOT NULL, is_canceled bool NOT NULL)",
            "CREATE TABLE affiliate_affiliateprofile (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, status varchar(20) NOT NULL,
             commission_rate decimal NOT NULL, facebook varchar(200) NULL, instagram varchar(200) NULL, twitter varchar(200) NULL,
             tiktok varchar(200) NULL, agreement_accepted bool NOT NULL, rejected_reason text NULL, created_at datetime NOT NULL,
             updated_at datetime NOT NULL, user_id bigint NOT NULL UNIQUE, affiliate_name varchar(13) NOT NULL UNIQUE)",
            "CREATE TABLE affiliate_affiliatelink (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, commission_rate decimal NOT NULL,
             clicks integer NOT NULL, is_active bool NOT NULL, created_at datetime NOT NULL, event_id char(32) NOT NULL, affiliate_id bigint NOT NULL)",
            "CREATE TABLE affiliate_affiliatesale (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, ticket_count integer NOT NULL,
             gross_amount decimal NOT NULL, commission_rate decimal NOT NULL, commission_amount decimal NOT NULL, status varchar(20) NOT NULL,
             created_at datetime NOT NULL, payable_at datetime NULL, paid_at datetime NULL, revoked_at datetime NULL,
             affiliate_id bigint NOT NULL, buyer_id bigint NOT NULL, event_id char(32) NOT NULL,
             issued_ticket_id char(32) NULL, link_id bigint NULL)",
        ] {
            sqlx::query(ddl).execute(&pool).await.unwrap();
        }
        for (email, code) in [("aff@example.com", "AFFAAA"), ("buy@example.com", "BUYBBB")] {
            sqlx::query(
                "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
                 is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, has_DVA)
                 VALUES ('x', 0, '', '', '2026-01-01 00:00:00', ?, 'S', 'O', 1, 0, 0, 'user', 1, '2026-01-01 00:00:00', 0, ?, 0, 0)",
            ).bind(email).bind(code).execute(&pool).await.unwrap();
        }
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1, 1)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO market_place_ticketvendor (id, is_verified, created_at, updated_at)
             VALUES ('ffffffffffffffffffffffffffffffff', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00')",
        ).execute(&pool).await.unwrap();
        // approved, past event
        sqlx::query(
            "INSERT INTO market_place_eventinfo (id, event_title, hosted_by, category, event_banner, event_date,
                    is_free, is_approved, created_at, vendor_id, event_mode, cancel_failed, cancel_processed,
                    cancel_refunded, cancel_status, cancel_total, is_canceled)
             VALUES ('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'Show', 'H', 'music', 'b.jpg', '2020-01-01 00:00:00',
                     0, 1, '2026-01-01 00:00:00', 'ffffffffffffffffffffffffffffffff', 'offline', 0, 0, 0, 'pending', 0, 0)",
        ).execute(&pool).await.unwrap();
        // future event (sweep must skip)
        sqlx::query(
            "INSERT INTO market_place_eventinfo (id, event_title, hosted_by, category, event_banner, event_date,
                    is_free, is_approved, created_at, vendor_id, event_mode, cancel_failed, cancel_processed,
                    cancel_refunded, cancel_status, cancel_total, is_canceled)
             VALUES ('ffffffffffffffffffffffffffffffff', 'Future', 'H', 'music', 'b.jpg', '2999-01-01 00:00:00',
                     0, 1, '2026-01-01 00:00:00', 'ffffffffffffffffffffffffffffffff', 'offline', 0, 0, 0, 'pending', 0, 0)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO affiliate_affiliateprofile (status, commission_rate, agreement_accepted, created_at, updated_at, user_id, affiliate_name)
             VALUES ('approved', '2.00', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1, 'Promo123')",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO affiliate_affiliatelink (commission_rate, clicks, is_active, created_at, event_id, affiliate_id)
             VALUES ('2.00', 0, 1, '2026-01-01 00:00:00', 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 1)",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn test_state(db: sqlx::SqlitePool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        config.debug = true;
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
        }
    }

    #[tokio::test]
    async fn attribution_complete_sweep_payout() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        let event = affiliate_models::event_by_id(&db, "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
            .await.unwrap().unwrap();

        // invalid: unknown name, self-purchase
        assert!(record_attribution(&db, 2, &event, "Nobody").await.unwrap().is_none());
        assert!(record_attribution(&db, 1, &event, "Promo123").await.unwrap().is_none());

        // valid click -> pending, clicks 1; repeat click -> same sale, clicks 2
        let a1 = record_attribution(&db, 2, &event, "Promo123").await.unwrap().unwrap();
        assert_eq!(a1.status, "pending");
        let a2 = record_attribution(&db, 2, &event, "Promo123").await.unwrap().unwrap();
        assert_eq!(a1.sale_id, a2.sale_id);
        let clicks: (i64,) = sqlx::query_as("SELECT clicks FROM affiliate_affiliatelink WHERE id = 1")
            .fetch_one(&db).await.unwrap();
        assert_eq!(clicks.0, 2);

        // purchase of ₦10000 completes: 2% = ₦200.00
        let sale = complete_sale(&db, 2, &event, "Promo123", None, 2, 1_000_000)
            .await.unwrap().unwrap();
        assert_eq!(sale, a1.sale_id);
        let row: (String, String, String, i64) = sqlx::query_as(
            "SELECT status, CAST(commission_amount AS TEXT), CAST(gross_amount AS TEXT), ticket_count
             FROM affiliate_affiliatesale WHERE id = ?",
        ).bind(sale).fetch_one(&db).await.unwrap();
        // NUMERIC affinity normalizes storage; output quantization happens
        // at serialization (dec2), like DRF's DecimalField.
        assert_eq!((row.0.as_str(), row.3), ("success", 2));
        assert_eq!(
            (
                crate::wallet::models::dec2(&row.1),
                crate::wallet::models::dec2(&row.2)
            ),
            ("200.00".to_string(), "10000.00".to_string())
        );

        // sweep (past event) -> payable; payout credits wallet 200
        assert_eq!(sweep_payable(&db, Some(1), "2026-06-01 00:00:00").await.unwrap(), 1);
        let (paid, total, reference) = pay_out(&s, 1, 1).await.unwrap();
        assert_eq!(paid.len(), 1);
        assert_eq!(total, "200.00");
        assert!(reference.unwrap().starts_with("AFF-"));
        let bal: (String,) = sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = 1")
            .fetch_one(&db).await.unwrap();
        assert_eq!(bal.0, "200");

        // second payout: nothing payable
        let (paid, total, reference) = pay_out(&s, 1, 1).await.unwrap();
        assert!(paid.is_empty() && reference.is_none());
        assert_eq!(total, "0.00");

        // revoke on already-paid: no-op
        assert!(revoke_sale(&db, "deadbeefdeadbeefdeadbeefdeadbeef", "2026-06-01 00:00:00").await.unwrap().is_none());
    }
}
