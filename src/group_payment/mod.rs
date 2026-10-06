//! Group payment app — payment groups and membership.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (groups, members; dashless UUID PKs)
//!   serializers.rs <-> response shapes (Django uses inline dicts)
//!   views.rs       <-> views.py (create, add-member, list, details,
//!                    update, join, leave, cancel)
//!   urls.rs        <-> urls.py (mounted at /payments/group/)
//! (`serializers.py`/`utils.py` are empty in Django — nothing to port.)

pub mod models;
pub mod serializers;
pub mod urls;
pub mod views;
