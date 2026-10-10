//! Marketplace app — vendors, events, tickets, scanning, withdrawals.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (6 tables, UUID UUID hex ids)
//!   serializers.rs <-> serializers.py
//!   utils.rs       <-> utils.py (HMAC QR payloads + QR PNG)
//!   tasks.rs       <-> tasks.py (expiry sweep, reminders, event-update
//!                    mail, cancellation refunds; Tokio tasks for Celery)
//!   views/*        <-> views.py (vendor / events / purchase / tickets /
//!                    scan / withdrawal)
//!   urls.rs        <-> urls.py (mounted at `/marketplace/`)
//!
//! Django-admin-only helpers (`admin.py`, `admin_views.py`) are not ported:
//! this backend has no Django admin (see README).

pub mod models;
pub mod serializers;
pub mod tasks;
pub mod urls;
pub mod utils;
pub mod views;
