//! View handlers for the accounts app (mirrors `accounts/views.py`),
//! split by concern:
//!   auth.rs   <-> RegisterView/LoginView/VerifyEmail/PasswordReset*
//!   social.rs <-> GoogleLoginView/AppleLoginView
//!   pin.rs    <-> transaction-PIN views
//!   lookup.rs <-> LookupUserView/DedicatedVirtualAccountAssignView

pub mod auth;
pub mod lookup;
pub mod pin;
pub mod social;
