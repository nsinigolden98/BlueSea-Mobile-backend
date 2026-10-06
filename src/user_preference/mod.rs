//! User preference app — profile extension.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (UpdateUserModel)
//!   serializers.rs <-> serializers.py (CurrentUser + preference shapes)
//!   views.rs       <-> views.py (GET/PATCH user/, GET check/<email>/)
//!   urls.rs        <-> urls.py

pub mod models;
pub mod serializers;
pub mod urls;
pub mod views;
