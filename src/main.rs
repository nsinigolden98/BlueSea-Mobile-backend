mod accounts;
mod affiliate;
mod auth;

mod autotopup;
mod bonus;
mod group_payment;
mod loyalty_market;
mod docs;
mod email;
mod error;
mod notifications;
mod payments;
mod settings;
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
    let db = sqlx::SqlitePool::connect(&config.database_url).await?;
    let http = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()?;
    let state = AppState {
        db,
        config,
        http,
        wallet_hub: wallet::hub::WalletHub::default(),
    };
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
