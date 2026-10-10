//! Loyalty engine. Mirrors `bonus/utils.py`:
//! point awards (with campaign multipliers), redemption to wallet,
//! referral/signup/daily-login bonuses, and the points summary.

use rust_decimal::Decimal;
use serde_json::{Value, json};

use crate::state::AppState;

use super::models as bonus_models;

fn dec(raw: &str) -> Decimal {
    bonus_models::dec(raw)
}

/// Lagos calendar date (Django `timezone.now().date()` under Africa/Lagos).
fn lagos_today() -> String {
    (chrono::Utc::now() + chrono::Duration::hours(1))
        .date_naive()
        .to_string()
}

fn lagos_now() -> String {
    crate::time::now_str()
}

async fn notify_earned(
    state: &AppState,
    user_id: i64,
    user_email: &str,
    first_name: &str,
    points_display: &str,
    description: &str,
) {
    let _ = crate::notifications::utils::send_notification(
        state,
        user_id,
        user_email,
        first_name,
        &format!("You earned {points_display} bonus points!"),
        description,
        "info",
        None,
        crate::notifications::utils::NotifyContext::default(),
    )
    .await;
}

async fn notify_redeemed(
    state: &AppState,
    user_id: i64,
    user_email: &str,
    first_name: &str,
    points_display: &str,
    description: &str,
) {
    let _ = crate::notifications::utils::send_notification(
        state,
        user_id,
        user_email,
        first_name,
        &format!("{points_display} points redeemed"),
        description,
        "wallet",
        None,
        crate::notifications::utils::NotifyContext::default(),
    )
    .await;
}

async fn profile_email(
    db: &sqlx::PgPool,
    user_id: i64,
) -> Option<(String, String)> {
    sqlx::query_as::<_, (String, String)>(
        "SELECT email, other_names FROM accounts_profile WHERE id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await
    .unwrap_or(None)
}

/// Core award: get-or-create account, apply the running campaign, bump
/// balances, write history, notify. Mirrors `award_points`.
#[allow(clippy::too_many_arguments)]
pub async fn award_points(
    state: &AppState,
    user_id: i64,
    points: Decimal,
    reason: &str,
    description: &str,
    reference: Option<&str>,
    metadata: Value,
    created_by: Option<i64>,
) -> Result<i64, String> {
    if points <= Decimal::ZERO {
        return Err("Points must be positive".to_string());
    }
    let now = lagos_now();
    let account = bonus_models::ensure_point(&state.db, user_id, &now)
        .await
        .map_err(|e| e.to_string())?;

    let mut final_points = points;
    let mut final_description = description.to_string();
    if let Some(campaign) = bonus_models::active_campaign(&state.db, &now)
        .await
        .map_err(|e| e.to_string())?
    {
        final_points = apply_campaign(&campaign, points);
        final_description = format!("{description} (Campaign: {})", campaign.name);
    }

    let before = dec(&account.points);
    let after = before + final_points;
    let lifetime = dec(&account.lifetime_earned) + final_points;
    bonus_models::set_point_balances(
        &state.db,
        account.id,
        &after.to_string(),
        &lifetime.to_string(),
        &account.lifetime_redeemed,
        &now,
    )
    .await
    .map_err(|e| e.to_string())?;

    let id = bonus_models::insert_history(
        &state.db,
        user_id,
        "earned",
        &final_points.to_string(),
        Some(reason),
        &final_description,
        reference,
        &before.to_string(),
        &after.to_string(),
        created_by,
        &metadata.to_string(),
        &now,
    )
    .await
    .map_err(|e| e.to_string())?;

    if let Some((email, first)) = profile_email(&state.db, user_id).await {
        notify_earned(
            state,
            user_id,
            &email,
            &first,
            &final_points.to_string(),
            &final_description,
        )
        .await;
    }
    tracing::info!("Awarded {final_points} points to user {user_id} for {reason}");
    Ok(id)
}

fn apply_campaign(
    campaign: &bonus_models::BonusCampaignRow,
    base: Decimal,
) -> Decimal {
    // is_running re-checked against Lagos now, like the model method.
    let now = lagos_now();
    let running = campaign.is_active
        && campaign.start_date.format("%Y-%m-%d %H:%M:%S%.f").to_string() <= now
        && now <= campaign.end_date.format("%Y-%m-%d %H:%M:%S%.f").to_string();
    if !running {
        return base;
    }
    match campaign.campaign_type.as_str() {
        "multiplier" => {
            let mult = dec(&campaign.multiplier);
            (base * mult).trunc()
        }
        "fixed_bonus" => base + dec(&campaign.bonus_amount),
        "percentage_bonus" => {
            let amt = dec(&campaign.bonus_amount);
            base + ((base * amt) / Decimal::from(100)).trunc()
        }
        _ => base,
    }
}

/// 1 point per ₦100 spent, quantized to 2dp. Mirrors
/// `award_vtu_purchase_points` (purchase in naira-cents).
pub async fn award_vtu_purchase_points(
    state: &AppState,
    user_id: i64,
    purchase_cents: i64,
    reference: &str,
) {
    let purchase = Decimal::from(purchase_cents) / Decimal::from(100);
    let points = (purchase / Decimal::from(100)).round_dp_with_strategy(
        2,
        rust_decimal::RoundingStrategy::MidpointNearestEven,
    );
    if points <= Decimal::ZERO {
        return;
    }
    if let Err(e) = award_points(
        state,
        user_id,
        points,
        "vtu_purchase",
        &format!("VTU purchase bonus for ₦{purchase} transaction"),
        Some(reference),
        json!({"purchase_amount": purchase.to_string()}),
        None,
    )
    .await
    {
        tracing::error!("Error awarding bonus points: {e}");
    }
}

/// 50-point referrer award + referral completion.
/// Mirrors `award_referral_bonus`.
pub async fn award_referral_bonus(
    state: &AppState,
    referrer_id: i64,
    referred_user_id: i64,
    referred_email: &str,
) {
    let referral = match bonus_models::pending_referral(&state.db, referrer_id, referred_user_id)
        .await
    {
        Ok(r) => r,
        Err(e) => {
            tracing::warn!("referral lookup failed: {e}");
            return;
        }
    };
    let Some(referral) = referral else {
        tracing::warn!("No referral record found for {referred_email}");
        return;
    };
    let now = lagos_now();
    match award_points(
        state,
        referrer_id,
        Decimal::from(50),
        "referral",
        &format!("Referral bonus for {referred_email} completing first transaction"),
        Some(&format!("REF-{referred_user_id}")),
        json!({"referred_user_id": referred_user_id}),
        None,
    )
    .await
    {
        Ok(_) => {
            let _ = bonus_models::complete_referral(&state.db, referral.id, &now).await;
        }
        Err(e) => tracing::warn!("referral award failed: {e}"),
    }
}

/// 20-point welcome bonus for referred signups. Mirrors `award_signup_bonus`.
/// Returns true when points were awarded.
pub async fn award_signup_bonus(state: &AppState, user_id: i64) -> bool {
    let referral = match bonus_models::referral_for_referred(&state.db, user_id).await {
        Ok(Some(r)) if r.status == "pending" => r,
        _ => return false,
    };
    let exists = bonus_models::signup_bonus_exists(&state.db, user_id, user_id)
        .await
        .unwrap_or(true);
    if exists {
        return false;
    }
    award_points(
        state,
        user_id,
        Decimal::from(20),
        "signup_bonus",
        "Welcome bonus for signing up with a referral",
        Some(&format!("SIGNUP-{user_id}")),
        json!({"referrer_id": referral.referrer_id}),
        None,
    )
    .await
    .is_ok()
}

/// Daily 10-point login bonus. Returns the new total on success, None when
/// already claimed today. Mirrors `award_daily_login_bonus`.
pub async fn award_daily_login_bonus(
    state: &AppState,
    user_id: i64,
) -> Result<Option<(Decimal, Decimal)>, String> {
    let now = lagos_now();
    let today = lagos_today();
    let account = bonus_models::ensure_point(&state.db, user_id, &now)
        .await
        .map_err(|e| e.to_string())?;
    if let Some(last) = account.last_daily_login {
        if last.to_string() >= today {
            tracing::info!("User {user_id} already claimed daily login bonus today");
            return Ok(None);
        }
    }
    let points = Decimal::from(10);
    award_points(
        state,
        user_id,
        points,
        "daily_login",
        "Daily login bonus",
        Some(&format!("DAILY-{user_id}-{today}")),
        Value::Null,
        None,
    )
    .await?;
    bonus_models::set_last_daily_login(&state.db, account.id, &today)
        .await
        .map_err(|e| e.to_string())?;
    let updated = bonus_models::get_point(&state.db, user_id)
        .await
        .map_err(|e| e.to_string())?;
    let total = updated.map(|p| dec(&p.points)).unwrap_or(Decimal::ZERO);
    Ok(Some((points, total)))
}

/// Mark a pending referral's first transaction as completed (flag only —
/// the bonus itself is awarded by `award_referral_bonus`).
/// Returns the referrer id when a pending referral was found.
pub async fn mark_first_transaction_completed(
    db: &sqlx::PgPool,
    referred_user_id: i64,
) -> Result<Option<i64>, sqlx::Error> {
    let row: Option<(i64, i64)> = sqlx::query_as(
        "SELECT id, referrer_id FROM bonus_referral
         WHERE referred_user_id = $1 AND status = 'pending' AND first_transaction_completed = 0",
    )
    .bind(referred_user_id)
    .fetch_optional(db)
    .await?;
    if let Some((id, referrer_id)) = row {
        sqlx::query("UPDATE bonus_referral SET first_transaction_completed = 1 WHERE id = $1")
            .bind(id)
            .execute(db)
            .await?;
        return Ok(Some(referrer_id));
    }
    Ok(None)
}

/// Redeem points to wallet at 10 points = ₦1. Only whole multiples.
/// Mirrors `redeem_points` (no live HTTP route — the view is commented out
/// in Django).
pub async fn redeem_points(
    state: &AppState,
    user_id: i64,
    points: i64,
) -> Result<(String, String), String> {
    if points <= 0 {
        return Err("Points must be positive".to_string());
    }
    if points % 10 != 0 {
        return Err("Points must be in multiples of 10".to_string());
    }
    let now = lagos_now();
    let account = bonus_models::get_point(&state.db, user_id)
        .await
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "Bonus account not found".to_string())?;
    if dec(&account.points) < Decimal::from(points) {
        return Err(format!(
            "Insufficient points. You have {} points.",
            account.points
        ));
    }
    let wallet_amount = Decimal::from(points) / Decimal::from(10);
    let before = dec(&account.points);
    let after = before - Decimal::from(points);
    let redeemed_total = dec(&account.lifetime_redeemed) + Decimal::from(points);
    bonus_models::set_point_balances(
        &state.db,
        account.id,
        &after.to_string(),
        &account.lifetime_earned,
        &redeemed_total.to_string(),
        &now,
    )
    .await
    .map_err(|e| e.to_string())?;

    let wallet: Option<(i64,)> = sqlx::query_as("SELECT id FROM wallet_wallet WHERE user_id = $1")
        .bind(user_id)
        .fetch_optional(&state.db)
        .await
        .map_err(|e| e.to_string())?;
    let Some((wallet_id,)) = wallet else {
        return Err("Wallet not found".to_string());
    };
    let reference = format!(
        "BP-REDEEM-{user_id}-{}",
        chrono::Utc::now().timestamp_micros() as f64 / 1_000_000.0
    );
    crate::wallet::models::credit(
        &state.db,
        &state.wallet_hub,
        wallet_id,
        user_id,
        &wallet_amount.to_string(),
        &format!("Bonus points redemption ({points} points)"),
        Some(&reference),
    )
    .await
    .map_err(|e| format!("{e:?}"))?;

    bonus_models::insert_history(
        &state.db,
        user_id,
        "redeemed",
        &points.to_string(),
        None,
        &format!("Points redeemed to wallet - Converted to ₦{wallet_amount}"),
        Some(&format!("BP-REDEEM-{user_id}")),
        &before.to_string(),
        &after.to_string(),
        None,
        &json!({"wallet_amount": wallet_amount.to_string(), "conversion_rate": 10}).to_string(),
        &now,
    )
    .await
    .map_err(|e| e.to_string())?;

    if let Some((email, first)) = profile_email(&state.db, user_id).await {
        notify_redeemed(
            state,
            user_id,
            &email,
            &first,
            &points.to_string(),
            &format!("You redeemed {points} points for ₦{wallet_amount}"),
        )
        .await;
    }
    Ok((points.to_string(), wallet_amount.to_string()))
}

/// Points summary for the summary endpoint. Mirrors `user_points_summary`,
/// including the `lifetime_earned` key (the schema doc says
/// `lifetime_record`, but the code returns `lifetime_earned`).
pub async fn user_points_summary(
    state: &AppState,
    user_id: i64,
) -> Result<Value, String> {
    let account = bonus_models::get_point(&state.db, user_id)
        .await
        .map_err(|e| e.to_string())?;
    let today = lagos_today();
    let (total, completed) = referral_counts(&state.db, user_id).await?;
    match account {
        Some(a) => {
            let rows: Vec<(
                String, String, String, String, String,
            )> = sqlx::query_as(
                "SELECT transaction_type, CAST(points AS TEXT), description, CAST(created_at AS TEXT), CAST(balance_after AS TEXT)
                 FROM bonus_bonushistory WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10",
            )
            .bind(user_id)
            .fetch_all(&state.db)
            .await
            .map_err(|e| e.to_string())?;
            let recent: Vec<Value> = rows
                .into_iter()
                .map(|(tt, pts, desc, created, _)| {
                    json!({
                        "bonus_type": tt,
                        "points": crate::wallet::models::dec2(&pts),
                        "description": desc,
                        "date": crate::transactions::serializers::format_created_at_lagos(&created),
                    })
                })
                .collect();
            let redeemable = (dec(&a.points) / Decimal::from(10)).to_string();
            let can_claim = a
                .last_daily_login
                .map(|d| d.to_string() < today)
                .unwrap_or(true);
            Ok(json!({
                "current_points": crate::wallet::models::dec2(&a.points),
                "lifetime_earned": crate::wallet::models::dec2(&a.lifetime_earned),
                "lifetime_redeemed": crate::wallet::models::dec2(&a.lifetime_redeemed),
                "redeemable_amount": redeemable,
                "can_claim_daily_login": can_claim,
                "last_daily_login": a.last_daily_login.map(|d| d.to_string()),
                "referral_count": total,
                "completed_referrals": completed,
                "recent_history": recent,
            }))
        }
        None => Ok(json!({
            "current_points": 0,
            "lifetime_earned": 0,
            "lifetime_redeemed": 0,
            "redeemable_amount": "0.00",
            "can_claim_daily_login": true,
            "last_daily_login": Value::Null,
            "referral_count": total,
            "completed_referrals": completed,
            "recent_history": [],
        })),
    }
}

async fn referral_counts(db: &sqlx::PgPool, user_id: i64) -> Result<(i64, i64), String> {    let total: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM bonus_referral WHERE referrer_id = $1")
        .bind(user_id)
        .fetch_optional(db)
        .await
        .map_err(|e| e.to_string())?
        .unwrap_or((0,));
    let completed: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM bonus_referral WHERE referrer_id = $1 AND status = 'completed'",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await
    .map_err(|e| e.to_string())?
    .unwrap_or((0,));
    Ok((total.0, completed.0))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;


async fn memory_db() -> sqlx::PgPool {
        let pool = crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, password varchar(128) NOT NULL,
             last_login TIMESTAMPTZ NULL, is_superuser BOOLEAN NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined TIMESTAMPTZ NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active BOOLEAN NOT NULL,
             is_staff BOOLEAN NOT NULL, is_admin BOOLEAN NOT NULL, role varchar(200) NOT NULL, email_verified BOOLEAN NOT NULL,
             created_on TIMESTAMPTZ NOT NULL, pin_is_set BOOLEAN NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until TIMESTAMPTZ NULL, nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL, utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE, frozen_reason varchar(200) NULL, \"has_DVA\" BOOLEAN NOT NULL)",
            "CREATE TABLE wallet_wallet (id BIGSERIAL PRIMARY KEY, balance NUMERIC NOT NULL,
             locked_balance NUMERIC NOT NULL, total_in NUMERIC NOT NULL DEFAULT 0, total_out NUMERIC NOT NULL DEFAULT 0,  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             is_active BOOLEAN NOT NULL, user_id bigint NOT NULL UNIQUE)",
            "CREATE TABLE transactions_wallettransaction (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             transaction_type varchar(6) NOT NULL, status varchar(10) NOT NULL, description text NULL,
             reference varchar(100) NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL, wallet_id bigint NOT NULL)",
            "CREATE TABLE notifications_notification (id BIGSERIAL PRIMARY KEY, title varchar(200) NOT NULL,
             message text NOT NULL, notification_type varchar(20) NOT NULL, is_read BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL,
             read_at TIMESTAMPTZ NULL, user_id bigint NOT NULL, broadcast_id bigint NULL)",
            "CREATE TABLE bonus_bonuspoint (id BIGSERIAL PRIMARY KEY, lifetime_earned NUMERIC NOT NULL,
             lifetime_redeemed NUMERIC NOT NULL, last_daily_login date NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             user_id bigint NOT NULL UNIQUE, points NUMERIC NOT NULL)",
            "CREATE TABLE bonus_bonushistory (id BIGSERIAL PRIMARY KEY, transaction_type varchar(20) NOT NULL,
             reason varchar(50) NULL, description text NOT NULL, reference varchar(100) NULL, balance_before NUMERIC NOT NULL,
             balance_after NUMERIC NOT NULL, created_at TIMESTAMPTZ NOT NULL, metadata text NULL, created_by_id bigint NULL, user_id bigint NOT NULL,
             points NUMERIC NOT NULL)",
            "CREATE TABLE bonus_bonuscampaign (id BIGSERIAL PRIMARY KEY, name varchar(200) NOT NULL,
             description text NOT NULL, campaign_type varchar(20) NOT NULL, bonus_amount NUMERIC NOT NULL, is_active BOOLEAN NOT NULL,
             start_date TIMESTAMPTZ NOT NULL, end_date TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
             multiplier NUMERIC NOT NULL)",
            "CREATE TABLE bonus_referral (id BIGSERIAL PRIMARY KEY, status varchar(20) NOT NULL,
             bonus_awarded BOOLEAN NOT NULL, first_transaction_completed BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL,
             completed_at TIMESTAMPTZ NULL, referred_user_id bigint NOT NULL UNIQUE, referrer_id bigint NOT NULL,
             count integer NOT NULL, referral_code varchar(20) NOT NULL)",
        ]).await;
        for (email, code) in [("ref@example.com", "REFERR"), ("new@example.com", "NEWWWW")] {
            sqlx::query(
                "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
                 is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, \"has_DVA\")
                 VALUES ('x', FALSE, '', '', '2026-01-01 00:00:00', $1, 'S', 'O', TRUE, FALSE, FALSE, 'user', TRUE, '2026-01-01 00:00:00', FALSE, $2, 0, FALSE)",
            ).bind(email).bind(code).execute(&pool).await.unwrap();
        }
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', TRUE, 2)",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn test_state(db: sqlx::PgPool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        config.debug = true;
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
            support_hub: crate::support::hub::SupportHub::default(),
            plans_store: crate::plans_cache::PlansStore::default(),
            notification_hub: crate::notifications::hub::NotificationHub::default(),
        }
    }

    #[tokio::test]
    async fn referral_signup_vtu_daily_redeem_flow() {
        let db = memory_db().await;
        let s = test_state(db.clone());

        // referred user applies referrer's code -> pending referral + 20 signup points
        sqlx::query(
            "INSERT INTO bonus_referral (status, bonus_awarded, first_transaction_completed, created_at, referred_user_id, referrer_id, count, referral_code)
             VALUES ('pending', FALSE, FALSE, '2026-01-01 00:00:00', 2, 1, 0, 'REFERR')",
        ).execute(&db).await.unwrap();
        assert!(award_signup_bonus(&s, 2).await);
        let pts: (String,) =
            sqlx::query_as("SELECT CAST(points AS TEXT) FROM bonus_bonuspoint WHERE user_id = 2")
                .fetch_one(&db).await.unwrap();
        assert_eq!(pts.0, "20");
        // second attempt: already awarded
        assert!(!award_signup_bonus(&s, 2).await);

        // VTU purchase of ₦500 -> 5.00 points (20 + 5 = 25)
        award_vtu_purchase_points(&s, 2, 50_000, "VTU-1").await;
        let pts: (String,) =
            sqlx::query_as("SELECT CAST(points AS TEXT) FROM bonus_bonuspoint WHERE user_id = 2")
                .fetch_one(&db).await.unwrap();
        assert_eq!(pts.0, "25");

        // referral bonus: 50 to referrer, referral completed
        award_referral_bonus(&s, 1, 2, "new@example.com").await;
        let rpts: (String,) =
            sqlx::query_as("SELECT CAST(points AS TEXT) FROM bonus_bonuspoint WHERE user_id = 1")
                .fetch_one(&db).await.unwrap();
        assert_eq!(rpts.0, "50");
        let st: (String, bool) =
            sqlx::query_as("SELECT status, bonus_awarded FROM bonus_referral WHERE referred_user_id = 2")
                .fetch_one(&db).await.unwrap();
        assert_eq!(st.0, "completed");
        assert_eq!(st.1, true);

        // daily login: 10 points once, then None
        let first = award_daily_login_bonus(&s, 2).await.unwrap();
        assert!(first.is_some());
        let second = award_daily_login_bonus(&s, 2).await.unwrap();
        assert!(second.is_none());

        // summary shape
        let summary = user_points_summary(&s, 2).await.unwrap();
        assert_eq!(summary["current_points"], "35.00");
        assert_eq!(summary["lifetime_earned"], "35.00");
        assert_eq!(summary["redeemable_amount"], "3.50");
        assert_eq!(summary["can_claim_daily_login"], false);
        assert_eq!(summary["recent_history"].as_array().unwrap().len(), 3);

        // redeem 20 points -> ₦2 wallet credit
        let (redeemed, wallet_amount) = redeem_points(&s, 2, 20).await.unwrap();
        assert_eq!((redeemed.as_str(), wallet_amount.as_str()), ("20", "2"));
        let bal: (String,) =
            sqlx::query_as("SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = 2")
                .fetch_one(&db).await.unwrap();
        assert_eq!(bal.0, "2.00");

        // invalid redemptions
        assert!(redeem_points(&s, 2, 15).await.is_err());
        assert!(redeem_points(&s, 2, 1000).await.is_err());
    }

    #[tokio::test]
    async fn campaign_multiplier_applies() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        sqlx::query(
            "INSERT INTO bonus_bonuscampaign (name, description, campaign_type, bonus_amount, is_active, start_date, end_date, created_at, updated_at, multiplier)
             VALUES ('Double', 'x2', 'multiplier', '0.00', TRUE, '2020-01-01 00:00:00', '2030-01-01 00:00:00', '2026-01-01 00:00:00', '2026-01-01 00:00:00', '2.00')",
        ).execute(&db).await.unwrap();
        award_vtu_purchase_points(&s, 2, 50_000, "VTU-C").await;
        let pts: (String,) =
            sqlx::query_as("SELECT CAST(points AS TEXT) FROM bonus_bonuspoint WHERE user_id = 2")
                .fetch_one(&db).await.unwrap();
        assert_eq!(pts.0, "10");
    }
}
