//! Accounts app — custom user + auth.
//! Django file layout mirrored:
//!   models.rs       <-> models.py
//!   serializers.rs  <-> serializers.py + social_serializers.py
//!   views.rs        <-> views.py (split by concern underneath)
//!   views/auth.rs   <-> RegisterView/LoginView/VerifyEmail/PasswordReset*
//!   views/social.rs <-> GoogleLoginView
//!   views/pin.rs    <-> transaction-PIN views
//!   views/lookup.rs <-> LookupUserView/DedicatedVirtualAccountAssignView
//!   urls.rs         <-> urls.py
//!   crypto.rs       <-> crypto.py (RSA PIN/BVN decrypt)
//!   pin_security.rs <-> pin_security.py (lockout)
//!   social_auth.rs  <-> social_auth.py (Google verification)
//!   utils.rs        <-> utils.py (OTP/email helpers)

pub mod crypto;
pub mod models;
pub mod pin_security;
pub mod serializers;
pub mod kyc;
pub mod social_auth;
pub mod tier;
pub mod urls;
pub mod utils;
pub mod views;
