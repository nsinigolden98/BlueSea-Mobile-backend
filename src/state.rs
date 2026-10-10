use crate::notifications::hub::NotificationHub;
use crate::plans_cache::PlansStore;
use crate::settings::Config;
use crate::support::hub::SupportHub;
use crate::wallet::hub::WalletHub;

#[derive(Clone)]
pub struct AppState {
    pub db: sqlx::PgPool,
    pub config: Config,
    pub http: reqwest::Client,
    pub wallet_hub: WalletHub,
    pub support_hub: SupportHub,
    pub notification_hub: NotificationHub,
    pub plans_store: PlansStore,
}
