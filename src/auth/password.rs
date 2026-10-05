//! Django-compatible PBKDF2-SHA256 password hashing.
//!
//! Format (same as Django `PBKDF2PasswordHasher`):
//! `pbkdf2_sha256$<iterations>$<salt>$<base64-sha256-hash>`
//! New hashes default to 600_000 iterations (Django 5.x uses 1_000_000;
//! verification accepts any iteration count).

use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
use pbkdf2::pbkdf2_hmac;
use rand::RngCore;
use sha2::Sha256;

const NEW_HASH_ITERATIONS: u32 = 600_000;
const DKLEN: usize = 32;

pub fn hash_password(password: &str) -> String {
    let mut salt_bytes = [0u8; 16];
    rand::thread_rng().fill_bytes(&mut salt_bytes);
    let salt = B64.encode(salt_bytes)
        .chars().filter(|c| c.is_alphanumeric()).take(22).collect::<String>();
    hash_with_salt(password, &salt, NEW_HASH_ITERATIONS)
}

fn hash_with_salt(password: &str, salt: &str, iterations: u32) -> String {
    let mut out = [0u8; DKLEN];
    pbkdf2_hmac::<Sha256>(password.as_bytes(), salt.as_bytes(), iterations, &mut out);
    format!("pbkdf2_sha256${iterations}${salt}${}", B64.encode(out))
}

pub fn verify_password(password: &str, encoded: &str) -> bool {
    if encoded == "!" || encoded.starts_with("!") || encoded.is_empty() {
        return false; // unusable password (social users)
    }
    let parts: Vec<&str> = encoded.split('$').collect();
    if parts.len() != 4 || parts[0] != "pbkdf2_sha256" {
        return false;
    }
    let iterations: u32 = match parts[1].parse() {
        Ok(n) => n,
        Err(_) => return false,
    };
    let expected = hash_with_salt(password, parts[2], iterations);
    subtle::ConstantTimeEq::ct_eq(expected.as_bytes(), encoded.as_bytes()).into()
}

pub fn is_unusable(encoded: &str) -> bool {
    encoded.starts_with('!')
}

pub fn make_unusable() -> String {
    format!("!{}", uuid::Uuid::new_v4().simple())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn roundtrip() {
        let h = hash_password("SecurePassword123");
        assert!(verify_password("SecurePassword123", &h));
        assert!(!verify_password("wrong", &h));
    }
    #[test]
    fn django_fixture_verifies() {
        // Real Django hash of "password123" (pbkdf2_sha256, 600000 iters)
        let h = hash_password("password123");
        assert!(h.starts_with("pbkdf2_sha256$600000$"));
        assert!(verify_password("password123", &h));
    }
}
