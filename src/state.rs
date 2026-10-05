use crate::settings::Config;
use crate::wallet::hub::WalletHub;

#[derive(Clone)]
pub struct AppState {
    pub db: sqlx::SqlitePool,
    pub config: Config,
    pub http: reqwest::Client,
    pub wallet_hub: WalletHub,
}
