//! Broadcast app — superuser mass mail + in-app notifications.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (Broadcast row)
//!   serializers.rs <-> serializers.py
//!   views.rs       <-> views.py (new-month / important / announcement / history)
//!   tasks.rs       <-> tasks.py (Celery fan-out, here a Tokio task)
//!   urls.rs        <-> urls.py
//!
//! Delivery replaces Celery with `tokio::spawn(tasks::send_broadcast)`:
//! one in-app Notification per active user plus one email each rendered
//! from the Askama port of the Django template. The view still returns
//! the record immediately with HTTP 202.

pub mod models;
pub mod serializers;
pub mod tasks;
pub mod urls;
pub mod views;
