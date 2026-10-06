//! Notifications app.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (Notification row)
//!   serializers.rs <-> serializers.py
//!   views.rs       <-> views.py (list, mark read, mark all, delete)
//!   urls.rs        <-> urls.py
//!   utils.rs       <-> utils.py (send + group notification emails)

pub mod models;
pub mod serializers;
pub mod urls;
pub mod utils;
pub mod views;
