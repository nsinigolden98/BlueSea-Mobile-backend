//! Notifications app (minimal port).
//! Django layout mirrored: `models.rs` <-> `models.py` (Notification row),
//! `utils.rs` <-> `utils.py::send_notification` (in-app row + email).
//! List/read/delete endpoints and background tasks land with the full
//! notifications app port.

pub mod models;
pub mod utils;
