//! Auto top-up app — scheduled airtime/data purchases with wallet locking.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (schedule, lock/unlock, history)
//!   serializers.rs <-> serializers.py (validation + shapes)
//!   views.rs       <-> views.py (create, list, detail/PUT/PATCH/DELETE,
//!                    cancel, reactivate, history)
//!   tasks.rs       <-> tasks.py (60s sweep + execution with retries)
//!   urls.rs        <-> urls.py

pub mod models;
pub mod serializers;
pub mod tasks;
pub mod urls;
pub mod views;
