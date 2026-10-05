mod accounts;
mod auth;
mod email;
mod error;
mod settings;
mod state;
mod urls;

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
    let state = AppState { db, config, http };
    let app = urls::router(state);
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8000").await?;
    tracing::info!("listening on {}", listener.local_addr()?);
    axum::serve(listener, app).await?;
    Ok(())
}
