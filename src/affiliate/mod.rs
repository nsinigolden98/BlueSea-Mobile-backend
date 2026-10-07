//! Affiliate app — event ticket referrals.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (profiles, links, sales)
//!   serializers.rs <-> serializers.py (validation + shapes)
//!   utils.rs       <-> utils.py (attribution, completion, sweep, payout)
//!   views.rs       <-> views.py (apply, status, links, attribution,
//!                    dashboard, sales, payout)
//!   urls.rs        <-> urls.py (mounted at /affiliate/)

pub mod models;
pub mod serializers;
pub mod urls;
pub mod utils;
pub mod views;
