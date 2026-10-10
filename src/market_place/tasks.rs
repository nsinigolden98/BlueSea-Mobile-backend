//! Marketplace background work. Mirrors `market_place/tasks.py`:
//! - `expire_past_event_tickets` — daily beat in Django (00:00); here an
//!   hourly idempotent sweep (single UPDATE, same end state).
//! - `send_event_reminder_notifications` — same TODO stub as Django
//!   (counts upcoming tickets in the next 24h, logs only).
//! - `send_event_update_notifications` — buyer/owner mail on venue/link/
//!   date changes (Tokio spawn instead of `.delay()`).
//! - `process_event_cancellation` — per-ticket wallet refunds + mail after
//!   the vendor lump-sum debit (Tokio spawn instead of `.delay()`).
//!   Idempotent: skips non-upcoming tickets; wallet credit dedupes on
//!   `refund-<ticket>` references.

use std::collections::HashMap;

use serde_json::Value;

use crate::state::AppState;
use crate::time::now_str;

/// Mark `upcoming` tickets `expired` once sales close (4h after event
/// start), keeping grace-window purchases scannable.
pub async fn expire_past_event_tickets(state: &AppState) -> String {
    let cutoff = (chrono::Utc::now() - chrono::Duration::hours(4))
        .naive_utc()
        .format("%Y-%m-%d %H:%M:%S%.f")
        .to_string();
    match sqlx::query(
        "UPDATE market_place_issuedticket SET status = 'expired'
         WHERE status = 'upcoming' AND event_id IN (
             SELECT id FROM market_place_eventinfo WHERE event_date < $1
         )",
    )
    .bind(crate::time::Ts(&cutoff))
    .execute(&state.db)
    .await
    {
        Ok(res) => {
            let n = res.rows_affected();
            if n > 0 {
                tracing::info!("expired {n} tickets for past events");
                format!("Expired {n} tickets")
            } else {
                tracing::info!("no tickets to expire");
                "No tickets to expire".to_string()
            }
        }
        Err(e) => {
            tracing::error!("ticket expiry sweep failed: {e}");
            "Expiry sweep failed".to_string()
        }
    }
}

/// Reminder stub (mirrors Django's TODO): counts tickets for events in the
/// next 24h and logs, sending nothing.
pub async fn send_event_reminder_notifications(state: &AppState) -> String {
    let now = now_str();
    let tomorrow = (chrono::Utc::now() + chrono::Duration::hours(24))
        .naive_utc()
        .format("%Y-%m-%d %H:%M:%S%.f")
        .to_string();
    let row: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM market_place_issuedticket t
         JOIN market_place_eventinfo e ON e.id = t.event_id
         WHERE t.status = 'upcoming' AND e.event_date >= $1 AND e.event_date <= $2",
    )
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&tomorrow))
    .fetch_one(&state.db)
    .await
    .unwrap_or((0,));
    tracing::info!("sent reminders for {} upcoming events", row.0);
    format!("Sent {} reminders", row.0)
}

fn update_detail(changes: &HashMap<String, Value>) -> String {
    let labels = [
        ("event_location", "venue"),
        ("meeting_link", "meeting link"),
        ("event_date", "date/time"),
    ];
    let mut lines = Vec::new();
    for (field, label) in labels {
        if changes.contains_key(field) {
            lines.push(format!("{label} changed"));
        }
    }
    if lines.is_empty() {
        "details updated".to_string()
    } else {
        lines.join("; ")
    }
}

async fn notify_profile(
    state: &AppState,
    user_id: i64,
    title: &str,
    message: &str,
    notification_type: &str,
) {
    let profile = crate::auth::extractor::get_profile(&state.db, user_id).await.ok();
    let (email, first_name) = match profile {
        Some(p) => (p.email.clone(), p.other_names.clone()),
        None => return,
    };
    let _ = crate::notifications::utils::send_notification(
        state,
        user_id,
        &email,
        &first_name,
        title,
        message,
        notification_type,
        Some(&format!("BlueSea Mobile - {title}")),
        crate::notifications::utils::NotifyContext::default(),
    )
    .await;
}

/// Mail upcoming ticket holders about a venue/link/date change.
pub async fn send_event_update_notifications(
    state: &AppState,
    event_hex: &str,
    changes: HashMap<String, Value>,
) -> String {
    let event = match crate::market_place::models::event_by_id(&state.db, event_hex).await.ok().flatten() {
        Some(e) => e,
        None => {
            tracing::error!("event update task: event {event_hex} not found");
            return "Event not found".to_string();
        }
    };
    let detail = update_detail(&changes);
    let title = format!("Event Updated: {}", event.event_title);
    let message = format!(
        "'{}' has been updated by the vendor ({detail}). Your tickets remain valid.",
        event.event_title
    );

    let buyer_ids: Vec<(Option<i64>,)> = sqlx::query_as(
        "SELECT DISTINCT purchased_by_id FROM market_place_issuedticket
         WHERE event_id = CAST($1 AS UUID) AND status = 'upcoming' AND purchased_by_id IS NOT NULL",
    )
    .bind(event_hex)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    let mut sent = 0;
    let mut buyer_emails = std::collections::HashSet::new();
    for (buyer_id,) in buyer_ids {
        let Some(uid) = buyer_id else { continue };
        notify_profile(state, uid, &title, &message, "info").await;
        if let Ok(profile) = crate::auth::extractor::get_profile(&state.db, uid).await {
            buyer_emails.insert(profile.email.to_lowercase());
        }
        sent += 1;
    }

    let owner_emails: Vec<(String,)> = sqlx::query_as(
        "SELECT DISTINCT owner_email FROM market_place_issuedticket
         WHERE event_id = CAST($1 AS UUID) AND status = 'upcoming'",
    )
    .bind(event_hex)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    let mut owners: Vec<String> = owner_emails
        .into_iter()
        .map(|r| r.0.trim().to_string())
        .filter(|e| !e.is_empty())
        .collect();
    owners.sort();
    owners.dedup();
    for owner_email in owners {
        if buyer_emails.contains(&owner_email.to_lowercase()) {
            continue;
        }
        let owner: Option<(i64,)> = sqlx::query_as(
            "SELECT id FROM accounts_profile WHERE LOWER(email) = LOWER($1)",
        )
        .bind(&owner_email)
        .fetch_optional(&state.db)
        .await
        .unwrap_or(None);
        if let Some((uid,)) = owner {
            notify_profile(state, uid, &title, &message, "info").await;
        } else {
            crate::notifications::utils::send_default_email(
                state,
                &owner_email,
                "",
                &title,
                &message,
                "info",
                &format!("BlueSea Mobile - {title}"),
            )
            .await;
        }
        sent += 1;
    }

    tracing::info!("event {event_hex} update mails sent to {sent} recipient(s)");
    format!("Notified {sent} recipient(s)")
}

/// Async payout + mail for a vendor-canceled event. Mirrors
/// `process_event_cancellation` (including the `refund-<ticket>` credit
/// references and the `completed` / `completed_with_failures` tail).
pub async fn process_event_cancellation(
    state: &AppState,
    event_hex: &str,
    reason: &str,
) -> String {
    let event = match crate::market_place::models::event_by_id(&state.db, event_hex).await.ok().flatten() {
        Some(e) => e,
        None => {
            tracing::error!("event cancellation task: event {event_hex} not found");
            return "Event not found".to_string();
        }
    };
    if !event.is_canceled {
        tracing::warn!("event cancellation task: event {event_hex} not canceled");
        return "Event not canceled; nothing to do".to_string();
    }
    let canceled_raw: Option<String> = sqlx::query_as(
        "SELECT CAST(canceled_at AS TEXT) FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)",
    )
    .bind(event_hex)
    .fetch_optional(&state.db)
    .await
    .unwrap_or(None)
    .and_then(|r: (Option<String>,)| r.0);
    let cutoff = canceled_raw.unwrap_or_else(now_str);

    let ticket_ids: Vec<(String,)> = sqlx::query_as(
        "SELECT id FROM market_place_issuedticket
         WHERE event_id = CAST($1 AS UUID) AND status = 'upcoming' AND created_at <= $2
         ORDER BY created_at ASC",
    )
    .bind(event_hex)
    .bind(crate::time::Ts(&cutoff))
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let now = now_str();
    let mut processed = 0i64;
    let mut refunded = 0i64;
    let mut failed = 0i64;
    let mut free = 0i64;
    let mut notify_jobs: Vec<(String, Option<i64>, String, String)> = Vec::new();

    for (ticket_hex,) in ticket_ids {
        let ticket = match crate::market_place::models::ticket_by_id(&state.db, &ticket_hex).await.ok().flatten() {
            Some(t) => t,
            None => continue,
        };
        if ticket.status != "upcoming" {
            continue;
        }
        let paid = ticket.ticket_type_id.is_some() && !event.is_free;
        if paid {
            let price_cents = match ticket.ticket_type_id.as_ref() {
                Some(tt_id) => {
                    let row: Option<(String,)> = sqlx::query_as(
                        "SELECT CAST(price AS TEXT) FROM market_place_tickettype WHERE id = CAST($1 AS UUID)",
                    )
                    .bind(tt_id)
                    .fetch_optional(&state.db)
                    .await
                    .unwrap_or(None);
                    row.and_then(|r| crate::wallet::models::parse_cents(&r.0).ok()).unwrap_or(0)
                }
                None => 0,
            };
            let buyer_id = match ticket.purchased_by_id {
                Some(id) => id,
                None => {
                    failed += 1;
                    continue;
                }
            };
            let wallet = match crate::wallet::models::get_by_user(&state.db, buyer_id).await.ok().flatten() {
                Some(w) => w,
                None => {
                    tracing::error!("event cancellation: no wallet for buyer {buyer_id} (ticket {ticket_hex})");
                    failed += 1;
                    continue;
                }
            };
            let amount = crate::wallet::models::cents_to_decimal(price_cents);
            let reference = format!("refund-{ticket_hex}");
            if let Err(e) = crate::wallet::models::credit(
                &state.db,
                &state.wallet_hub,
                wallet.id,
                buyer_id,
                &amount,
                &format!("Refund: '{}' canceled by vendor", event.event_title),
                Some(&reference),
            )
            .await
            {
                tracing::error!("event cancellation refund failed for ticket {ticket_hex}: {e:?}");
                failed += 1;
                continue;
            }
            if let Some(tt_id) = &ticket.ticket_type_id {
                let _ = sqlx::query(
                    "UPDATE market_place_tickettype SET quantity_available = quantity_available + 1 WHERE id = CAST($1 AS UUID)",
                )
                .bind(tt_id)
                .execute(&state.db)
                .await;
            }
            if let Err(e) = crate::affiliate::utils::revoke_sale(&state.db, &ticket_hex, &now).await {
                tracing::error!("affiliate revoke failed for ticket {ticket_hex}: {e}");
            }
            let _ = sqlx::query(
                "UPDATE market_place_issuedticket
                 SET status = 'canceled', canceled_at = $1, cancellation_reason = $2, refund_amount = CAST($3 AS NUMERIC)
                 WHERE id = CAST($4 AS UUID)",
            )
            .bind(crate::time::Ts(&now))
            .bind(reason)
            .bind(&amount)
            .bind(&ticket_hex)
            .execute(&state.db)
            .await;
            refunded += 1;
            notify_jobs.push((ticket_hex, ticket.purchased_by_id, ticket.owner_email, amount));
        } else {
            let _ = sqlx::query(
                "UPDATE market_place_issuedticket
                 SET status = 'canceled', canceled_at = $1, cancellation_reason = $2, refund_amount = '0.00'
                 WHERE id = CAST($3 AS UUID)",
            )
            .bind(crate::time::Ts(&now))
            .bind(reason)
            .bind(&ticket_hex)
            .execute(&state.db)
            .await;
            free += 1;
            notify_jobs.push((ticket_hex, ticket.purchased_by_id, ticket.owner_email, "0.00".to_string()));
        }
        processed += 1;
    }

    for (ticket_hex, buyer_id, owner_email, refund_amount) in notify_jobs {
        let title = format!("Event Canceled: {}", event.event_title);
        let is_free_ticket = crate::wallet::models::parse_cents(&refund_amount).unwrap_or(0) <= 0;
        let message = if is_free_ticket {
            format!("'{}' has been canceled by the vendor. Reason: {reason}", event.event_title)
        } else {
            format!(
                "'{}' has been canceled by the vendor. ₦{refund_amount} has been refunded to your wallet. Reason: {reason}",
                event.event_title
            )
        };
        if let Some(uid) = buyer_id {
            if crate::auth::extractor::get_profile(&state.db, uid).await.is_ok() {
                notify_profile(state, uid, &title, &message, "warning").await;
            }
        }
        let owner_email = owner_email.trim().to_string();
        let buyer_email = match buyer_id {
            Some(uid) => crate::auth::extractor::get_profile(&state.db, uid).await.ok().map(|p| p.email.to_lowercase()),
            None => None,
        };
        if !owner_email.is_empty()
            && Some(owner_email.to_lowercase()) != buyer_email
        {
            let owner: Option<(i64,)> = sqlx::query_as(
                "SELECT id FROM accounts_profile WHERE LOWER(email) = LOWER($1)",
            )
            .bind(&owner_email)
            .fetch_optional(&state.db)
            .await
            .unwrap_or(None);
            if let Some((uid,)) = owner {
                notify_profile(state, uid, &title, &message, "warning").await;
            } else {
                crate::notifications::utils::send_default_email(
                    state,
                    &owner_email,
                    "",
                    &title,
                    &message,
                    "warning",
                    &format!("BlueSea Mobile - {title}"),
                )
                .await;
            }
        }
        let _ = ticket_hex;
    }

    let status = if failed == 0 { "completed" } else { "completed_with_failures" };
    let _ = sqlx::query(
        "UPDATE market_place_eventinfo
         SET cancel_status = $1, cancel_processed = $2, cancel_refunded = $3, cancel_failed = $4
         WHERE id = CAST($5 AS UUID)",
    )
    .bind(status)
    .bind(processed)
    .bind(refunded)
    .bind(failed)
    .bind(event_hex)
    .execute(&state.db)
    .await;
    tracing::info!(
        "event {event_hex} cancellation {status}: {processed} processed ({refunded} refunded, {free} free), {failed} failed"
    );
    format!("{status}: {processed} processed ({refunded} refunded, {free} free), {failed} failed")
}
