//! Transactions app — wallet history and Paystack funding.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (WalletTransaction, FundWallet)
//!   serializers.rs <-> serializers.py (live serializers)
//!   pagination.rs  <-> pagination.py (5 default / 50 max)
//!   paystack.rs    <-> paystack.py (checkout, resolve, DVA requery)
//!   views.rs       <-> views.py (split by concern underneath)
//!   urls.rs        <-> urls.py
//! (`utils.py` is fully commented out in Django — nothing to port.)

pub mod models;
pub mod pagination;
pub mod paystack;
pub mod serializers;
pub mod urls;
pub mod views;
