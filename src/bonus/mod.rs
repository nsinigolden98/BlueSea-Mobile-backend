//! Loyalty app — points, campaigns, referrals.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (points, history, campaigns, referrals)
//!   serializers.rs <-> serializers.py
//!   utils.rs       <-> utils.py (awards, redemption, summary)
//!   views.rs       <-> views.py (summary, history, daily-login, campaigns,
//!                    referral)
//!   urls.rs        <-> urls.py
//! (Django signals live as explicit calls: bonus accounts are created at
//! signup, VTU awards fire from the purchase paths.)

pub mod models;
pub mod serializers;
pub mod urls;
pub mod utils;
pub mod views;
