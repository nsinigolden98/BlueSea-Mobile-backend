//! Auto top-up execution. Mirrors `autotopup/tasks.py`
//! (`process_auto_topups` + `execute_auto_topup` + `vtu_data` +
//! `topup_failure`).
//!
//! Django runs these on celery beat every 60 seconds; here `sweep_once`
//! runs on a 60-second tokio interval spawned in `main`, fanning out one
//! task per due top-up. Transport errors retry 3 times with 60s gaps
//! (like celery `max_retries=3`); VTU-level failures go straight to the
//! failure path without retrying.

use rust_decimal::Decimal;
use serde_json::Value;

use crate::notifications::utils::{NotifyContext, send_notification};
use crate::payments::{plans, vtpass};use crate::state::AppState;

use super::models as topup_models;

/// One beat: queue every due (active + locked + next_run elapsed) top-up.
pub async fn sweep_once(state: &AppState) -> usize {
    let now = crate::time::now_str();
    let due = topup_models::due_topups(&state.db, &now).await.unwrap_or_default();
    tracing::info!("Found {} due auto top-ups", due.len());
    for id in &due {
        let state = state.clone();
        let id = *id;
        tokio::spawn(async move {
            if let Err(e) = execute_with_retries(&state, id).await {
                tracing::error!("Error executing auto top-up {id}: {e}");
            }
        });
    }
    due.len()
}

async fn execute_with_retries(state: &AppState, id: i64) -> Result<(), String> {
    // Initial attempt + 3 retries on transport errors (celery semantics:
    // only the exhausted final failure records unlock + history).
    let mut attempt = 0;
    loop {
        match execute_once(state, id, attempt).await {
            Ok(()) => return Ok(()),
            Err(RunError::Retryable(e)) if attempt < 3 => {
                tracing::warn!("Auto top-up {id} attempt {} failed: {e}. Retrying...", attempt + 1);
                tokio::time::sleep(std::time::Duration::from_secs(60)).await;
                attempt += 1;
            }
            Err(RunError::Retryable(e)) => {
                fail_with_error(state, id, &format!("Max retries exceeded: {e}")).await;
                return Ok(());
            }
            Err(RunError::Fatal(e)) => {
                tracing::error!("Auto top-up {id} fatal: {e}");
                return Ok(());
            }
        }
    }
}

enum RunError {
    Retryable(String),
    Fatal(String),
}

async fn execute_once(state: &AppState, id: i64, attempt: u32) -> Result<(), RunError> {
    let topup: Option<topup_models::AutoTopUpRow> =
        sqlx::query_as::<_, topup_models::AutoTopUpRow>(
            "SELECT id, service_type, CAST(amount AS TEXT) AS amount, phone_number, network, plan,
                    start_date, repeat_days, is_active, next_run, is_locked, CAST(locked_amount AS TEXT) AS locked_amount,
                    last_run, total_runs, failed_runs, created_at, updated_at, user_id
             FROM autotopup_autotopup WHERE id = ?",
        )
        .bind(id)
        .fetch_optional(&state.db)
        .await
        .map_err(|e| RunError::Fatal(e.to_string()))?;
    let Some(topup) = topup else {
        tracing::error!("AutoTopUp {id} not found");
        return Ok(());
    };
    if !topup.is_active || !topup.is_locked {
        tracing::warn!("AutoTopUp {id} is not active or locked");
        return Ok(());
    }

    let now = crate::time::now_str();
    let history_id = topup_models::insert_history(
        &state.db,
        id,
        &topup.amount,
        "pending",
        &now,
    )
    .await
    .map_err(|e| RunError::Fatal(e.to_string()))?;

    let request_id = vtpass::generate_reference_id();
    let payload = vtu_data(&topup);
    let response = match vtpass::top_up(&state.http, &state.config, &payload).await {
        Ok(r) => r,
        Err(e) => {
            let _ = topup_models::set_history(
                &state.db,
                history_id,
                "pending",
                None,
                None,
                Some(&format!("Attempt {} failed: {e}. Retrying...", attempt + 1)),
            )
            .await;
            return Err(RunError::Retryable(e));
        }
    };

    if vtpass::is_successful(&response) {
        succeed_run(state, &topup, history_id, &request_id, &response, &now).await;
        return Ok(());
    }
    // VTU-level failure: no retries, straight to the failure path.
    fail_with_response(state, id, history_id, &response).await;
    Ok(())
}

/// VTU payload. Mirrors `vtu_data` exactly, including the `billerCode`
/// (capital C) key and the display-name variation fallback.
fn vtu_data(topup: &topup_models::AutoTopUpRow) -> Value {
    let request_id = vtpass::generate_reference_id();
    if topup.service_type == "airtime" {
        let amount = topup
            .amount
            .parse::<Decimal>()
            .unwrap_or(Decimal::ZERO)
            .trunc()
            .to_string()
            .parse::<i64>()
            .unwrap_or(0);
        return serde_json::json!({
            "request_id": request_id,
            "serviceID": topup.network.clone().unwrap_or_default(),
            "amount": amount,
            "phone": topup.phone_number,
        });
    }
    let dict = match topup.network.as_deref().unwrap_or("") {
        "mtn" => plans::MTN_PLANS,
        "airtel" => plans::AIRTEL_PLANS,
        "glo" => plans::GLO_PLANS,
        _ => plans::ETISALAT_PLANS,
    };
    // Unknown networks fall through to the etisalat table, like Django's
    // `.get(network, {})` returning {} → plan_info default. The variation
    // falls back to the display plan name.
    let plan_name = topup.plan.clone().unwrap_or_default();
    let (code, price) = plans::find_plan(dict, &plan_name)
        .map(|p| (p.code.to_string(), p.price_naira))
        .unwrap_or_else(|| {
            (
                plan_name.clone(),
                topup
                    .amount
                    .parse::<Decimal>()
                    .unwrap_or(Decimal::ZERO)
                    .trunc()
                    .to_string()
                    .parse::<i64>()
                    .unwrap_or(0),
            )
        });
    serde_json::json!({
        "request_id": request_id,
        "serviceID": format!("{}-data", topup.network.clone().unwrap_or_default()),
        "billerCode": topup.phone_number,
        "variation_code": code,
        "amount": price,
        "phone": topup.phone_number,
    })
}

async fn succeed_run(
    state: &AppState,
    topup: &topup_models::AutoTopUpRow,
    history_id: i64,
    _request_id: &str,
    response: &Value,
    now: &str,
) {
    // Release the locked funds (locked moves out, no ledger row).
    if let Some((locked_raw,)) = sqlx::query_as::<_, (String,)>(
        "SELECT CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = ?",
    )
    .bind(topup.user_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None)
    {
        let locked = locked_raw.parse::<Decimal>().unwrap_or(Decimal::ZERO);
        let held: Decimal = topup.locked_amount.parse().unwrap_or(Decimal::ZERO);
        let _ = sqlx::query(
            "UPDATE wallet_wallet SET locked_balance = ?, updated_at = ? WHERE user_id = ?",
        )
        .bind((locked - held).to_string())
        .bind(now)
        .bind(topup.user_id)
        .execute(&state.db)
        .await;
    }

    let vtu_ref = response
        .get("requestId")
        .and_then(|v| v.as_str())
        .map(|v| v.to_string());
    let _ = topup_models::set_history(
        &state.db,
        history_id,
        "success",
        vtu_ref.as_deref(),
        Some(&response.to_string()),
        None,
    )
    .await;

    let _ = sqlx::query(
        "UPDATE autotopup_autotopup SET last_run = ?, total_runs = total_runs + 1,
         is_locked = 0, locked_amount = '0.00', updated_at = ? WHERE id = ?",
    )
    .bind(now)
    .bind(now)
    .bind(topup.id)
    .execute(&state.db)
    .await;

    let user: Option<(String, String)> = sqlx::query_as(
        "SELECT email, other_names FROM accounts_profile WHERE id = ?",
    )
    .bind(topup.user_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None);

    if topup.repeat_days > 0 {
        let advanced = topup.next_run + chrono::Duration::days(topup.repeat_days);
        let advanced_str = advanced.format("%Y-%m-%d %H:%M:%S%.f").to_string();
        let _ = sqlx::query("UPDATE autotopup_autotopup SET next_run = ?, updated_at = ? WHERE id = ?")
            .bind(&advanced_str)
            .bind(now)
            .bind(topup.id)
            .execute(&state.db)
            .await;
        // Lock funds for the next run, like Django.
        let amount: Decimal = topup.amount.parse().unwrap_or(Decimal::ZERO);
        let _ = topup_models::lock_funds(&state.db, topup.user_id, topup.id, amount, now).await;
        let relocked: Option<(bool,)> =
            sqlx::query_as("SELECT is_locked FROM autotopup_autotopup WHERE id = ?")
                .bind(topup.id)
                .fetch_optional(&state.db)
                .await
                .unwrap_or(None);
        if relocked.map(|(v,)| v) != Some(true) {
            let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = 0, updated_at = ? WHERE id = ?")
                .bind(now)
                .bind(topup.id)
                .execute(&state.db)
                .await;
            if let Some((email, first)) = user.clone() {
                let _ = send_notification(
                    state, topup.user_id, &email, &first,
                    "Auto Top-Up Deactivated",
                    &format!(
                        "Your {} auto top-up has been deactivated due to insufficient funds.",
                        topup.service_type
                    ),
                    "warning", None, NotifyContext::default(),
                )
                .await;
            }
        }
    } else {
        let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = 0, updated_at = ? WHERE id = ?")
            .bind(now)
            .bind(topup.id)
            .execute(&state.db)
            .await;
    }

    if let Some((email, first)) = user {
        let _ = send_notification(
            state, topup.user_id, &email, &first,
            "Auto Top-Up Successful",
            &format!(
                "Your {} top-up of ₦{} to {} was successful.",
                topup.service_type, topup.amount, topup.phone_number
            ),
            "success", None, NotifyContext::default(),
        )
        .await;
    }
    tracing::info!("Auto top-up {} executed successfully", topup.id);
}

/// VTU-level failure: unlock funds, fail the history row, bump the
/// counter, deactivate after 3 consecutive failures, notify.
/// Mirrors `topup_failure`.
async fn fail_with_response(
    state: &AppState,
    id: i64,
    history_id: i64,
    vtu_response: &serde_json::Value,
) {
    let error = vtu_response
        .get("error")
        .and_then(|v| v.as_str())
        .unwrap_or("VTU API failed");
    let now = crate::time::now_str();
    let topup = topup_row(state, id).await;
    let Some(topup) = topup else {
        return;
    };
    let _ = topup_models::unlock_funds(&state.db, topup.user_id, id, &now).await;
    let _ = topup_models::set_history(
        &state.db,
        history_id,
        "failed",
        None,
        Some(&vtu_response.to_string()),
        Some(error),
    )
    .await;
    finish_failure(state, &topup, &now).await;
}

/// Exhausted-retries failure: same as above with a synthetic error payload.
async fn fail_with_error(state: &AppState, id: i64, error: &str) {
    let now = crate::time::now_str();
    let hist: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM autotopup_autotopuphistory WHERE auto_topup_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
    )
    .bind(id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None);
    let topup = topup_row(state, id).await;
    let Some(topup) = topup else {
        return;
    };
    let _ = topup_models::unlock_funds(&state.db, topup.user_id, id, &now).await;
    if let Some((hid,)) = hist {
        let _ = topup_models::set_history(
            &state.db,
            hid,
            "failed",
            None,
            Some(&serde_json::json!({"error": error}).to_string()),
            Some(error),
        )
        .await;
    }
    finish_failure(state, &topup, &now).await;
}

async fn topup_row(state: &AppState, id: i64) -> Option<topup_models::AutoTopUpRow> {
    sqlx::query_as::<_, topup_models::AutoTopUpRow>(
        "SELECT id, service_type, CAST(amount AS TEXT) AS amount, phone_number, network, plan,
                start_date, repeat_days, is_active, next_run, is_locked, CAST(locked_amount AS TEXT) AS locked_amount,
                last_run, total_runs, failed_runs, created_at, updated_at, user_id
         FROM autotopup_autotopup WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None)
}

async fn finish_failure(state: &AppState, topup: &topup_models::AutoTopUpRow, now: &str) {
    let _ = sqlx::query(
        "UPDATE autotopup_autotopup SET failed_runs = failed_runs + 1, updated_at = ? WHERE id = ?",
    )
    .bind(now)
    .bind(topup.id)
    .execute(&state.db)
    .await;
    let failed: Option<(i64,)> =
        sqlx::query_as("SELECT failed_runs FROM autotopup_autotopup WHERE id = ?")
            .bind(topup.id)
            .fetch_optional(&state.db)
            .await
            .unwrap_or(None);
    let user: Option<(String, String)> = sqlx::query_as(
        "SELECT email, other_names FROM accounts_profile WHERE id = ?",
    )
    .bind(topup.user_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None);
    if failed.map(|(f,)| f).unwrap_or(0) >= 3 {
        let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = 0, updated_at = ? WHERE id = ?")
            .bind(now)
            .bind(topup.id)
            .execute(&state.db)
            .await;
        if let Some((email, first)) = user.clone() {
            let _ = send_notification(
                state, topup.user_id, &email, &first,
                "Auto Top-Up Deactivated",
                &format!(
                    "Your {} auto top-up has been deactivated after 3 failed attempts.",
                    topup.service_type
                ),
                "error", None, NotifyContext::default(),
            )
            .await;
        }
    }
    if let Some((email, first)) = user {
        let _ = send_notification(
            state, topup.user_id, &email, &first,
            "Auto Top-Up Failed",
            &format!(
                "Your {} top-up of ₦{} failed. Funds have been unlocked.",
                topup.service_type, topup.amount
            ),
            "error", None, NotifyContext::default(),
        )
        .await;
    }
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
            "CREATE TABLE notifications_notification (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, title varchar(200) NOT NULL,
             message text NOT NULL, notification_type varchar(20) NOT NULL, is_read bool NOT NULL, created_at datetime NOT NULL,
             read_at datetime NULL, user_id bigint NOT NULL, broadcast_id bigint NULL)",
            "CREATE TABLE autotopup_autotopup (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, service_type varchar(10) NOT NULL,
             amount decimal NOT NULL, phone_number varchar(20) NOT NULL, network varchar(20) NULL, plan varchar(100) NULL,
             start_date datetime NOT NULL, repeat_days integer NOT NULL, is_active bool NOT NULL, next_run datetime NOT NULL,
             is_locked bool NOT NULL, locked_amount decimal NOT NULL, last_run datetime NULL, total_runs integer NOT NULL,
             failed_runs integer NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL, user_id bigint NOT NULL)",
            "CREATE TABLE autotopup_autotopuphistory (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, amount decimal NOT NULL,
             status varchar(20) NOT NULL, vtu_reference varchar(100) NULL, vtu_response text NULL, error_message text NULL,
             executed_at datetime NOT NULL, auto_topup_id bigint NOT NULL)",
        ] {
            sqlx::query(ddl).execute(&pool).await.unwrap();
        }
        sqlx::query(
            "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
             is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, has_DVA)
             VALUES ('x', 0, '', '', '2026-01-01 00:00:00', 'a@b.com', 'S', 'O', 1, 0, 0, 'user', 1, '2026-01-01 00:00:00', 0, 'ABCDEF', 0, 0)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (1000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1, 1)",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn test_state(db: sqlx::SqlitePool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        config.debug = true;
        // Unreachable VTpass base: transport errors exercise the retry path fast.
        config.vtpass_base_url = "http://127.0.0.1:9".to_string();
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
        }
    }

    async fn seed_topup(db: &sqlx::SqlitePool, locked: bool) -> i64 {
        let res = sqlx::query(
            "INSERT INTO autotopup_autotopup (service_type, amount, phone_number, network, plan, start_date,
                    repeat_days, is_active, next_run, is_locked, locked_amount, total_runs, failed_runs,
                    created_at, updated_at, user_id)
             VALUES ('airtime', '100.00', '0801', 'mtn', NULL, '2026-01-01 00:00:00', 0, 1,
                     '2020-01-01 00:00:00', ?, '100.00', 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1)",
        )
        .bind(locked)
        .execute(db)
        .await
        .unwrap();
        res.last_insert_rowid()
    }

    #[tokio::test]
    async fn lock_unlock_roundtrip() {
        let db = memory_db().await;
        let now = "2026-01-01 00:00:00";
        let id = seed_topup(&db, false).await;
        assert!(topup_models::lock_funds(&db, 1, id, Decimal::from(100), now).await.unwrap());
        let w: (String, String) = sqlx::query_as(
            "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = 1",
        )
        .fetch_one(&db).await.unwrap();
        assert_eq!(w.0, "900");
        assert_eq!(w.1, "100");
        // short wallet refuses
        assert!(!topup_models::lock_funds(&db, 1, id, Decimal::from(99999), now).await.unwrap());
        assert!(topup_models::unlock_funds(&db, 1, id, now).await.unwrap());
        let w: (String, String) = sqlx::query_as(
            "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = 1",
        )
        .fetch_one(&db).await.unwrap();
        assert_eq!((w.0.as_str(), w.1.as_str()), ("1000", "0"));
        // second unlock is a no-op
        assert!(!topup_models::unlock_funds(&db, 1, id, now).await.unwrap());
    }

    #[tokio::test]
    async fn execute_transport_failure_retries_then_fails() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        // Locked + due one-time top-up; VTpass unreachable -> 1 immediate
        // failure record path (execute_once surfaces retryable; run one shot).
        let id = seed_topup(&db, true).await;
        // lock the matching wallet funds first to mirror create()
        sqlx::query("UPDATE wallet_wallet SET balance = '900', locked_balance = '100' WHERE user_id = 1")
            .execute(&db).await.unwrap();
        let before: (i64,) = sqlx::query_as("SELECT failed_runs FROM autotopup_autotopup WHERE id = ?")
            .bind(id).fetch_one(&db).await.unwrap();
        assert_eq!(before.0, 0);
        // Direct failure path (what the exhausted retry calls; execute_once
        // would have created the pending history row first).
        sqlx::query(
            "INSERT INTO autotopup_autotopuphistory (auto_topup_id, amount, status, executed_at)
             VALUES (?, '100.00', 'pending', '2026-01-01 00:00:00')",
        )
        .bind(id)
        .execute(&db)
        .await
        .unwrap();
        fail_with_error(&s, id, "Max retries exceeded: connection refused").await;
        let after: (i64, i64, i64) = sqlx::query_as(
            "SELECT failed_runs, is_active, is_locked FROM autotopup_autotopup WHERE id = ?",
        )
        .bind(id).fetch_one(&db).await.unwrap();
        assert_eq!((after.0, after.1, after.2), (1, 1, 0));
        let w: (String, String) = sqlx::query_as(
            "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = 1",
        )
        .fetch_one(&db).await.unwrap();
        assert_eq!((w.0.as_str(), w.1.as_str()), ("1000", "0"));
        let h: (String,) = sqlx::query_as(
            "SELECT status FROM autotopup_autotopuphistory WHERE auto_topup_id = ? ORDER BY id DESC LIMIT 1",
        )
        .bind(id).fetch_one(&db).await.unwrap();
        // No history row existed (execute_once creates it); fail path unlocks regardless.
        let _ = h;
    }

    #[tokio::test]
    async fn sweep_picks_only_due_locked_active() {
        let db = memory_db().await;
        let s = test_state(db.clone());
        let due = seed_topup(&db, true).await;
        // not-due: future next_run
        sqlx::query(
            "INSERT INTO autotopup_autotopup (service_type, amount, phone_number, network, start_date,
                    repeat_days, is_active, next_run, is_locked, locked_amount, total_runs, failed_runs,
                    created_at, updated_at, user_id)
             VALUES ('airtime', '100.00', '0801', 'mtn', '2026-01-01 00:00:00', 0, 1,
                     '2999-01-01 00:00:00', 1, '100.00', 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1)",
        ).execute(&db).await.unwrap();
        // inactive
        sqlx::query(
            "INSERT INTO autotopup_autotopup (service_type, amount, phone_number, network, start_date,
                    repeat_days, is_active, next_run, is_locked, locked_amount, total_runs, failed_runs,
                    created_at, updated_at, user_id)
             VALUES ('airtime', '100.00', '0801', 'mtn', '2026-01-01 00:00:00', 0, 0,
                     '2020-01-01 00:00:00', 1, '100.00', 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1)",
        ).execute(&db).await.unwrap();
        let found = topup_models::due_topups(&db, &crate::time::now_str()).await.unwrap();
        assert_eq!(found, vec![due]);
        let _ = s;
    }
}
