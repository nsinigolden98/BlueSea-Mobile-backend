//! Loyalty hooks (minimal stub).
//! Mirrors the call sites in `payments/views.py` + `payments/webhook.py`
//! (`bonus.utils.award_vtu_purchase_points`, `award_referral_bonus`, and the
//! `Referral.first_transaction_completed` flag write). Point awards land with
//! the full bonus app port; the referral flag side-effect is preserved now
//! because later bonus logic depends on it.

pub mod utils;
