//! KYC tiers. Tier is derived from evidence on the profile (one-way):
//! - Tier 0: no phone number
//! - Tier 1: phone number
//! - Tier 2: + NIN (RSA-encrypted at rest)
//! - Tier 3: + BVN (RSA-encrypted at rest)
//! - Tier 4: + house address + utility-bill image
//!
//! Limits apply to cumulative lifetime totals, both directions:
//! T0/T1 ₦100,000 · T2 ₦1,000,000 · T3 ₦5,000,000 · T4 unlimited.
//! Frozen accounts move no money until an admin unfreezes them.

use crate::accounts::models::Profile;

/// Limits in kobo.
pub const T0_T1_LIMIT_CENTS: i64 = 10_000_000;
pub const T2_LIMIT_CENTS: i64 = 100_000_000;
pub const T3_LIMIT_CENTS: i64 = 500_000_000;

pub fn tier_of(profile: &Profile) -> u8 {
    let has_phone = profile.phone.as_deref().map(|p| !p.trim().is_empty()).unwrap_or(false);
    if !has_phone {
        return 0;
    }
    let has_nin = profile.nin_encrypted.as_deref().map(|v| !v.is_empty()).unwrap_or(false);
    if !has_nin {
        return 1;
    }
    let has_bvn = profile.bvn_encrypted.as_deref().map(|v| !v.is_empty()).unwrap_or(false);
    if !has_bvn {
        return 2;
    }
    let has_address = profile.house_address.as_deref().map(|v| !v.trim().is_empty()).unwrap_or(false);
    let has_bill = profile.utility_bill_image.as_deref().map(|v| !v.is_empty()).unwrap_or(false);
    if !(has_address && has_bill) {
        return 3;
    }
    4
}

/// Cumulative in/out cap in kobo, or `None` for unlimited (tier 4).
pub fn limit_cents(profile: &Profile) -> Option<i64> {
    match tier_of(profile) {
        0 | 1 => Some(T0_T1_LIMIT_CENTS),
        2 => Some(T2_LIMIT_CENTS),
        3 => Some(T3_LIMIT_CENTS),
        _ => None,
    }
}

pub fn limit_naira_display(limit_cents: i64) -> String {
    format!("₦{}", limit_cents / 100)
}

/// What's still missing for the next tier (for the KYC status response).
pub fn missing_items(profile: &Profile) -> Vec<&'static str> {
    match tier_of(profile) {
        0 => vec!["phone_number"],
        1 => vec!["nin"],
        2 => vec!["bvn"],
        3 => {
            let mut v = Vec::new();
            if profile.house_address.as_deref().map(|s| s.trim().is_empty()).unwrap_or(true) {
                v.push("house_address");
            }
            if profile.utility_bill_image.as_deref().map(|v| v.is_empty()).unwrap_or(true) {
                v.push("utility_bill");
            }
            v
        }
        _ => vec![],
    }
}

/// 11-digit NIN/BVN format check (before RSA encryption at rest).
pub fn valid_nin_bvn(v: &str) -> bool {
    v.len() == 11 && v.bytes().all(|b| b.is_ascii_digit())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn profile() -> Profile {
        Profile {
            id: 1,
            password: String::new(),
            last_login: None,
            is_superuser: false,
            first_name: String::new(),
            last_name: String::new(),
            date_joined: crate::time::NaiveUtc(
                chrono::NaiveDateTime::parse_from_str("2026-01-01 00:00:00", "%Y-%m-%d %H:%M:%S").unwrap(),
            ),
            email: "t@t.com".to_string(),
            surname: String::new(),
            other_names: String::new(),
            phone: None,
            image: None,
            verification_code: None,
            is_active: true,
            is_staff: false,
            is_admin: false,
            role: "user".to_string(),
            email_verified: true,
            created_on: crate::time::NaiveUtc(
                chrono::NaiveDateTime::parse_from_str("2026-01-01 00:00:00", "%Y-%m-%d %H:%M:%S").unwrap(),
            ),
            pin_is_set: false,
            transaction_pin: None,
            referral_code: "ABCDEF".to_string(),
            pin_failed_attempts: 0,
            pin_locked_until: None,
            has_dva: false,
            nin_encrypted: None,
            bvn_encrypted: None,
            house_address: None,
            utility_bill_image: None,
            is_frozen: false,
            frozen_reason: None,
        }
    }

    #[test]
    fn tier_ladder() {
        let mut p = profile();
        assert_eq!(tier_of(&p), 0);
        assert_eq!(limit_cents(&p), Some(T0_T1_LIMIT_CENTS));
        p.phone = Some("0801".to_string());
        assert_eq!(tier_of(&p), 1);
        p.nin_encrypted = Some("enc".to_string());
        assert_eq!(tier_of(&p), 2);
        assert_eq!(limit_cents(&p), Some(T2_LIMIT_CENTS));
        p.bvn_encrypted = Some("enc".to_string());
        assert_eq!(tier_of(&p), 3);
        assert_eq!(limit_cents(&p), Some(T3_LIMIT_CENTS));
        p.house_address = Some("12 Main St".to_string());
        assert_eq!(tier_of(&p), 3);
        assert_eq!(missing_items(&p), vec!["utility_bill"]);
        p.utility_bill_image = Some("kyc/1.jpg".to_string());
        assert_eq!(tier_of(&p), 4);
        assert_eq!(limit_cents(&p), None);
        assert!(missing_items(&p).is_empty());
        assert!(valid_nin_bvn("12345678901"));
        assert!(!valid_nin_bvn("12345"));
        assert!(!valid_nin_bvn("1234567890a"));
    }
}
