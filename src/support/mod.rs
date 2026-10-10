//! Support app — tickets, messages, attachments + live chat.
//! Django file layout mirrored:
//!   models.rs      <-> models.py (SupportTicket, SupportMessage, SupportAttachment)
//!   serializers.rs <-> serializers.py
//!   views.rs       <-> views.py + admin_view.py (user + admin REST)
//!   urls.rs        <-> urls.py
//!   routing.rs     <-> routing.py (ws/support/, ws/support/<ticket_id>/)
//!   consumers.rs   <-> consumers.py (live chat)
//!   hub.rs         <-> channels groups `support_ticket_<id>`, `support_user_<id>`

pub mod consumers;
pub mod hub;
pub mod models;
pub mod routing;
pub mod serializers;
pub mod urls;
pub mod views;
