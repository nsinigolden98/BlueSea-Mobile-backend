mod accounts;
mod admin;
mod affiliate;
mod auth;

mod autotopup;
mod bonus;
mod broadcast;
mod db;
mod market_place;
mod group_payment;
mod loyalty_market;
mod docs;
mod email;
mod error;
mod notifications;
mod payments;
mod plans_cache;
mod settings;
mod support;
mod user_preference;
mod state;
mod time;
mod transactions;
mod urls;
mod wallet;

use state::AppState;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt().with_env_filter("info").init();
    let config = settings::Config::from_env();
    tracing::info!("debug={} db={}", config.debug, config.database_url);
    let db = db::connect(&config.database_url).await?;
    // Schema is owned by sqlx migrations (./migrations). Baseline covers the
    // full Django-migrated schema; new changes ship as `sqlx migrate add`
    // files. Runs on every boot; applied migrations are skipped via
    // `_sqlx_migrations`, so this is a no-op when up to date.
    sqlx::migrate!("./migrations").run(&db).await?;
    let http = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()?;
    let state = AppState {
        db,
        config,
        http,
        wallet_hub: wallet::hub::WalletHub::default(),
        support_hub: support::hub::SupportHub::default(),
        notification_hub: notifications::hub::NotificationHub::default(),
        plans_store: plans_cache::PlansStore::default(),
    };
    // Plans cache: fetch all 8 Nomba plan lists at startup (empty cache on
    // failure — the server still starts), then refresh every 6 hours.
    // Skipped when PLANS_SCHEDULER=0 (extra replicas).
    state.plans_store.warm(&state.config).await;
    if std::env::var("PLANS_SCHEDULER").as_deref() != Ok("0") {
        let refresher = state.clone();
        tokio::spawn(async move {
            let mut tick = tokio::time::interval(std::time::Duration::from_secs(6 * 3600));
            loop {
                tick.tick().await;
                refresher.plans_store.warm(&refresher.config).await;
            }
        });
    }
    // Auto top-up beat (mirrors celery beat's 60s `process_auto_topups`).
    // Skipped when the AUTOTOPUP_SCHEDULER env var is "0" (e.g. extra replicas).
    if std::env::var("AUTOTOPUP_SCHEDULER").as_deref() != Ok("0") {
        let beat = state.clone();
        tokio::spawn(async move {
            let mut tick =
                tokio::time::interval(std::time::Duration::from_secs(60));
            loop {
                tick.tick().await;
                autotopup::tasks::sweep_once(&beat).await;
            }
        });
    }
    // Marketplace sweeps (Celery beat ran expiry daily at 00:00 and the
    // reminder stub daily at 09:00). Expiry runs hourly here — the sweep is
    // an idempotent single UPDATE with the same end state. Skipped when
    // MARKETPLACE_SCHEDULER=0 (extra replicas).
    if std::env::var("MARKETPLACE_SCHEDULER").as_deref() != Ok("0") {
        let expiry = state.clone();
        tokio::spawn(async move {
            let mut tick = tokio::time::interval(std::time::Duration::from_secs(3600));
            loop {
                tick.tick().await;
                market_place::tasks::expire_past_event_tickets(&expiry).await;
            }
        });
        let reminders = state.clone();
        tokio::spawn(async move {
            let mut tick = tokio::time::interval(std::time::Duration::from_secs(86400));
            loop {
                tick.tick().await;
                market_place::tasks::send_event_reminder_notifications(&reminders).await;
            }
        });
    }
    let app = urls::router(state);
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8000);
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{port}")).await?;
    tracing::info!("listening on {}", listener.local_addr()?);
    axum::serve(listener, app).await?;
    Ok(())
}
