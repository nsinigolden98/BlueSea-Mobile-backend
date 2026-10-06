//! Loyalty market app — points redemption shop.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (rewards, redemptions; dashless UUID PKs)
//!   serializers.rs <-> serializers.py
//!   views.rs       <-> views.py (list, detail, redeem, my redemptions)
//!   urls.rs        <-> urls.py (mounted at /loyalty/)
//! (`permissions.py` belongs to the market-place app and lands there.)

pub mod models;
pub mod serializers;
pub mod urls;
pub mod views;
