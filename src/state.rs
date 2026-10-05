use crate::settings::Config;

#[derive(Clone)]
pub struct AppState {
    pub db: sqlx::SqlitePool,
    pub config: Config,
    pub http: reqwest::Client,
}
