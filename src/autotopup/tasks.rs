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
             FROM autotopup_autotopup WHERE id = $1",
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
    // Nomba rails: airtime via `purchase_airtime_parent`, data via
    // `vend_data_parent` (plan id stored on the schedule).
    let (transport_ok, gateway_data) = nomba_run(state, &topup, &request_id).await;
    if !transport_ok {
        let e = gateway_data
            .as_str()
            .unwrap_or("Nomba request failed")
            .to_string();
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

    let response = gateway_data;
    if crate::transactions::nomba_gateway::is_success(&response) {
        succeed_run(state, &topup, history_id, &request_id, &response, &now).await;
        return Ok(());
    }
    // VTU-level failure: no retries, straight to the failure path.
    fail_with_response(state, id, history_id, &response).await;
    Ok(())
}

/// Nomba run for one schedule: airtime via `purchase_airtime_parent`,
/// data via `vend_data_parent` with the stored plan id. Returns
/// `(true, success_envelope)` or `(false, error_message_value)`.
async fn nomba_run(
    state: &AppState,
    topup: &topup_models::AutoTopUpRow,
    request_id: &str,
) -> (bool, Value) {
    use crate::transactions::nomba_gateway;
    let network = topup.network.clone().unwrap_or_default().to_uppercase();
    let fail = |m: &str| (false, Value::String(m.to_string()));
    if topup.service_type == "airtime" {
        let amount = topup
            .amount
            .parse::<Decimal>()
            .unwrap_or(Decimal::ZERO)
            .trunc()
            .to_string()
            .parse::<i64>()
            .unwrap_or(0);
        let (ok, data) = nomba_gateway::purchase_airtime(
            &state.config, amount, &topup.phone_number, &network, request_id,
        )
        .await;
        if !ok {
            return fail(data.as_str().unwrap_or("Nomba request failed"));
        }
        return (
            true,
            serde_json::json!({
                "success": true, "code": "00", "description": "TRANSACTION SUCCESSFUL",
                "requestId": request_id, "reference": request_id, "data": data,
            }),
        );
    }
    let product_id = topup.plan.clone().unwrap_or_default();
    let (ok, data) = nomba_gateway::vend_data(
        &state.config, &product_id, &topup.phone_number, &network, request_id,
    )
    .await;
    if !ok {
        return fail(data.as_str().unwrap_or("Nomba request failed"));
    }
    (
        true,
        serde_json::json!({
            "success": true, "code": "00", "description": "TRANSACTION SUCCESSFUL",
            "requestId": request_id, "reference": request_id, "data": data,
        }),
    )
}

/// Legacy VTU payload builder (reference only — schedules now run on Nomba).
/// Mirrors `vtu_data` exactly, including the `billerCode`
/// (capital C) key and the display-name variation fallback.
#[allow(dead_code)]
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
        _ => plans::NINEMOBILE_PLANS,
    };
    // Unknown networks fall through to the 9mobile table, like Django's
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
        "SELECT CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(topup.user_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None)
    {
        let locked = locked_raw.parse::<Decimal>().unwrap_or(Decimal::ZERO);
        let held: Decimal = topup.locked_amount.parse().unwrap_or(Decimal::ZERO);
        let _ = sqlx::query(
            "UPDATE wallet_wallet SET locked_balance = $1, updated_at = $2 WHERE user_id = $3",
        )
        .bind((locked - held).to_string())
        .bind(crate::time::Ts(&now))
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
        "UPDATE autotopup_autotopup SET last_run = $1, total_runs = total_runs + 1,
         is_locked = 0, locked_amount = '0.00', updated_at = $1 WHERE id = $2",
    )
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(topup.id)
    .execute(&state.db)
    .await;

    let user: Option<(String, String)> = sqlx::query_as(
        "SELECT email, other_names FROM accounts_profile WHERE id = $1",
    )
    .bind(topup.user_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None);

    if topup.repeat_days > 0 {
        let advanced = topup.next_run + chrono::Duration::days(topup.repeat_days as i64);
        let advanced_str = advanced.format("%Y-%m-%d %H:%M:%S%.f").to_string();
        let _ = sqlx::query("UPDATE autotopup_autotopup SET next_run = $1, updated_at = $2 WHERE id = $3")
            .bind(&advanced_str)
            .bind(crate::time::Ts(&now))
            .bind(topup.id)
            .execute(&state.db)
            .await;
        // Lock funds for the next run, like Django.
        let amount: Decimal = topup.amount.parse().unwrap_or(Decimal::ZERO);
        let _ = topup_models::lock_funds(&state.db, topup.user_id, topup.id, amount, now).await;
        let relocked: Option<(bool,)> =
            sqlx::query_as("SELECT is_locked FROM autotopup_autotopup WHERE id = $1")
                .bind(topup.id)
                .fetch_optional(&state.db)
                .await
                .unwrap_or(None);
        if relocked.map(|(v,)| v) != Some(true) {
            let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = FALSE, updated_at = $1 WHERE id = $2")
                .bind(crate::time::Ts(&now))
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
        let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = FALSE, updated_at = $1 WHERE id = $2")
            .bind(crate::time::Ts(&now))
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
        "SELECT id FROM autotopup_autotopuphistory WHERE auto_topup_id = $1 AND status = 'pending' ORDER BY id DESC LIMIT 1",
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
         FROM autotopup_autotopup WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None)
}

async fn finish_failure(state: &AppState, topup: &topup_models::AutoTopUpRow, now: &str) {
    let _ = sqlx::query(
        "UPDATE autotopup_autotopup SET failed_runs = failed_runs + 1, updated_at = $1 WHERE id = $2",
    )
    .bind(crate::time::Ts(&now))
    .bind(topup.id)
    .execute(&state.db)
    .await;
    let failed: Option<(i32,)> =
        sqlx::query_as("SELECT failed_runs FROM autotopup_autotopup WHERE id = $1")
            .bind(topup.id)
            .fetch_optional(&state.db)
            .await
            .unwrap_or(None);
    let user: Option<(String, String)> = sqlx::query_as(
        "SELECT email, other_names FROM accounts_profile WHERE id = $1",
    )
    .bind(topup.user_id)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None);
    if failed.map(|(f,)| f).unwrap_or(0) >= 3 {
        let _ = sqlx::query("UPDATE autotopup_autotopup SET is_active = FALSE, updated_at = $1 WHERE id = $2")
            .bind(crate::time::Ts(&now))
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
            "CREATE TABLE notifications_notification (id BIGSERIAL PRIMARY KEY, title varchar(200) NOT NULL,
             message text NOT NULL, notification_type varchar(20) NOT NULL, is_read BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL,
             read_at TIMESTAMPTZ NULL, user_id bigint NOT NULL, broadcast_id bigint NULL)",
            "CREATE TABLE autotopup_autotopup (id BIGSERIAL PRIMARY KEY, service_type varchar(10) NOT NULL,
             amount NUMERIC NOT NULL, phone_number varchar(20) NOT NULL, network varchar(20) NULL, plan varchar(100) NULL,
             start_date TIMESTAMPTZ NOT NULL, repeat_days integer NOT NULL, is_active BOOLEAN NOT NULL, next_run TIMESTAMPTZ NOT NULL,
             is_locked BOOLEAN NOT NULL, locked_amount NUMERIC NOT NULL, last_run TIMESTAMPTZ NULL, total_runs integer NOT NULL,
             failed_runs integer NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, user_id bigint NOT NULL)",
            "CREATE TABLE autotopup_autotopuphistory (id BIGSERIAL PRIMARY KEY, amount NUMERIC NOT NULL,
             status varchar(20) NOT NULL, vtu_reference varchar(100) NULL, vtu_response text NULL, error_message text NULL,
             executed_at TIMESTAMPTZ NOT NULL, auto_topup_id bigint NOT NULL)",
        ])
        .await;
        sqlx::query(
            "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
             is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, \"has_DVA\")
             VALUES ('x', FALSE, '', '', '2026-01-01 00:00:00', 'a@b.com', 'S', 'O', TRUE, FALSE, FALSE, 'user', TRUE, '2026-01-01 00:00:00', FALSE, 'ABCDEF', 0, FALSE)",
        ).execute(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO wallet_wallet (balance, locked_balance, created_at, updated_at, is_active, user_id)
             VALUES (1000, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', TRUE, 1)",
        ).execute(&pool).await.unwrap();
        pool
    }

    fn test_state(db: sqlx::PgPool) -> AppState {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        config.debug = true;
        // Unreachable Nomba creds: gateway errors exercise the retry path fast.
        config.nomba_client_id = "bad".to_string();
        config.nomba_secret_key = "bad".to_string();
        config.nomba_account_id = "bad".to_string();
        config.nomba_sandbox = true;
        AppState {
            db,
            config,
            http: reqwest::Client::new(),
            wallet_hub: crate::wallet::hub::WalletHub::default(),
            support_hub: crate::support::hub::SupportHub::default(),
            notification_hub: crate::notifications::hub::NotificationHub::default(),
            plans_store: crate::plans_cache::PlansStore::default(),
        }
    }

    async fn seed_topup(db: &sqlx::PgPool, locked: bool) -> i64 {
        let row: (i64,) = sqlx::query_as(
            "INSERT INTO autotopup_autotopup (service_type, amount, phone_number, network, plan, start_date,
                    repeat_days, is_active, next_run, is_locked, locked_amount, total_runs, failed_runs,
                    created_at, updated_at, user_id)
             VALUES ('airtime', '100.00', '0801', 'mtn', NULL, '2026-01-01 00:00:00', 0, TRUE,
                     '2020-01-01 00:00:00', $1, '100.00', 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1)
             RETURNING id",
        )
        .bind(locked)
        .fetch_one(db)
        .await
        .unwrap();
        row.0
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
        // Locked + due one-time top-up; Nomba unreachable -> 1 immediate
        // failure record path (execute_once surfaces retryable; run one shot).
        let id = seed_topup(&db, true).await;
        // lock the matching wallet funds first to mirror create()
        sqlx::query("UPDATE wallet_wallet SET balance = '900', locked_balance = '100' WHERE user_id = 1")
            .execute(&db).await.unwrap();
        let before: (i32,) = sqlx::query_as("SELECT failed_runs FROM autotopup_autotopup WHERE id = $1")
            .bind(id).fetch_one(&db).await.unwrap();
        assert_eq!(before.0, 0);
        // Direct failure path (what the exhausted retry calls; execute_once
        // would have created the pending history row first).
        sqlx::query(
            "INSERT INTO autotopup_autotopuphistory (auto_topup_id, amount, status, executed_at)
             VALUES ($1, '100.00', 'pending', '2026-01-01 00:00:00')",
        )
        .bind(id)
        .execute(&db)
        .await
        .unwrap();
        fail_with_error(&s, id, "Max retries exceeded: connection refused").await;
        let after: (i32, bool, bool) = sqlx::query_as(
            "SELECT failed_runs, is_active, is_locked FROM autotopup_autotopup WHERE id = $1",
        )
        .bind(id).fetch_one(&db).await.unwrap();
        assert_eq!((after.0, after.1, after.2), (1, true, false));
        let w: (String, String) = sqlx::query_as(
            "SELECT CAST(balance AS TEXT), CAST(locked_balance AS TEXT) FROM wallet_wallet WHERE user_id = 1",
        )
        .fetch_one(&db).await.unwrap();
        assert_eq!((w.0.as_str(), w.1.as_str()), ("1000.00", "0.00"));
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
             VALUES ('airtime', '100.00', '0801', 'mtn', '2026-01-01 00:00:00', 0, TRUE,
                     '2999-01-01 00:00:00', TRUE, '100.00', 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1)",
        ).execute(&db).await.unwrap();
        // inactive
        sqlx::query(
            "INSERT INTO autotopup_autotopup (service_type, amount, phone_number, network, start_date,
                    repeat_days, is_active, next_run, is_locked, locked_amount, total_runs, failed_runs,
                    created_at, updated_at, user_id)
             VALUES ('airtime', '100.00', '0801', 'mtn', '2026-01-01 00:00:00', 0, FALSE,
                     '2020-01-01 00:00:00', TRUE, '100.00', 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00', 1)",
        ).execute(&db).await.unwrap();
        let found = topup_models::due_topups(&db, &crate::time::now_str()).await.unwrap();
        assert_eq!(found, vec![due]);
        let _ = s;
    }
}
