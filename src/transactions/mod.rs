//! Transactions app — wallet history and Nomba funding.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (WalletTransaction, FundWallet)
//!   serializers.rs <-> serializers.py (live serializers)
//!   pagination.rs  <-> pagination.py (5 default / 50 max)
//!   nomba_gateway.rs <-> nomba_gateway.py (async nomba-rs client)
//!   nomba_views.rs <-> nomba_views.py (funding, DVA, webhook)
//!   views.rs       <-> history only (Paystack rails removed)
//!   urls.rs        <-> urls.py
//! (`utils.py` is fully commented out in Django — nothing to port.)

pub mod models;
pub mod nomba_gateway;
pub mod nomba_views;
pub mod pagination;
pub mod serializers;
pub mod urls;
pub mod views;
