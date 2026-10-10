//! Payments app — VTU/bills, transfers, withdrawals.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (14 purchase tables, group, withdrawal,
//!                    transfer, customer, webhook log)
//!   plans.rs       <-> vtpass.py plan dicts (GENERATED, with prices)
//!   serializers.rs <-> serializers.py (DRF-shaped validation)
//!   vtpass.rs      <-> vtpass.py (API client)
//!   views.rs       <-> views.py (split by concern underneath)
//!   webhook.rs     <-> webhook.py (VTpass transaction-update)
//!   urls.rs        <-> urls.py
//! (Django's celery `tasks.py` is dead code — the views call VTpass
//! synchronously — so no worker is ported.)

pub mod models;
pub mod nomba_withdrawal;
pub mod plans;
pub mod serializers;
pub mod urls;
pub mod views;
pub mod vtpass;
pub mod webhook;
