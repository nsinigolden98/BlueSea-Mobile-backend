//! Wallet app — per-user ledger balances.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (Wallet row, credit/debit, pushes)
//!   serializers.rs <-> serializers.py
//!   views.rs       <-> views.py (GET balance/)
//!   consumers.rs   <-> consumers.py (balance WS)
//!   urls.rs        <-> urls.py
//!   routing.rs     <-> routing.py
//!   hub.rs         <-> Channels group layer (in-process broadcast)

pub mod consumers;
pub mod hub;
pub mod models;
pub mod routing;
pub mod serializers;
pub mod urls;
pub mod views;
