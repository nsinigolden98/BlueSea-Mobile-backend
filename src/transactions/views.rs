//! View handlers for the transactions app (mirrors `transactions/views.py`),
//! split by concern:
//!   history.rs      <-> GetWalletTransaction
//!   funding.rs      <-> InitializeFunding
//!   webhook.rs      <-> PaymentWebhook (excluded from OpenAPI, like Django)
//!   dva_refresh.rs  <-> DvaRefreshView
//!   account_name.rs <-> AccountNameView

pub mod account_name;
pub mod dva_refresh;
pub mod funding;
pub mod history;
pub mod webhook;
