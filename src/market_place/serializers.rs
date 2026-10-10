//! Marketplace response shapes. Mirrors `market_place/serializers.py`.

use serde::Serialize;
use utoipa::ToSchema;
use base64::Engine as _;

use crate::transactions::serializers::format_created_at_lagos;
use crate::wallet::models::dec2;

use super::models as m;

fn absolute(scheme: &str, host: &str, stored: &str) -> String {
    format!("{scheme}://{host}/media/{stored}")
}

async fn raw(
    db: &sqlx::PgPool,
    table: &str,
    col: &str,
    id_hex: &str,
) -> Option<String> {
    let sql = format!("SELECT CAST({col} AS TEXT) FROM {table} WHERE id = $1");
    sqlx::query_as::<_, (Option<String>,)>(&sql)
        .bind(id_hex)
        .fetch_optional(db)
        .await
        .ok()
        .flatten()
        .and_then(|r| r.0)
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct TicketTypePublic {
    pub id: String,
    pub name: String,
    pub price: String,
    pub quantity_available: i32,
    pub initial_quantity: i32,
    pub description: Option<String>,
    pub created_at: String,
}

pub async fn ticket_type_public(db: &sqlx::PgPool, t: &m::TicketType) -> TicketTypePublic {
    let created_at = raw(db, "market_place_tickettype", "created_at", &t.id)
        .await
        .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&t.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    TicketTypePublic {
        id: m::dashed(&t.id),
        name: t.name.clone(),
        price: dec2(&t.price),
        quantity_available: t.quantity_available,
        initial_quantity: t.initial_quantity,
        description: t.description.clone(),
        created_at,
    }
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct VendorPublicOut {
    pub id: String,
    pub brand_name: Option<String>,
    pub business_type: Option<String>,
    pub is_verified: bool,
    pub verification_status: Option<String>,
}

pub fn vendor_public(v: &m::TicketVendor) -> VendorPublicOut {
    VendorPublicOut {
        id: m::dashed(&v.id),
        brand_name: v.brand_name.clone(),
        business_type: v.business_type.clone(),
        is_verified: v.is_verified,
        verification_status: v.verification_status.clone(),
    }
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct EventPublic {
    pub id: String,
    pub vendor: VendorPublicOut,
    pub event_title: String,
    pub event_description: Option<String>,
    pub event_date: String,
    pub event_mode: String,
    pub event_location: Option<String>,
    pub meeting_link: Option<String>,
    pub hosted_by: String,
    pub category: String,
    pub is_free: bool,
    pub quantity: Option<i32>,
    pub event_banner: Option<String>,
    pub ticket_image: Option<String>,
    pub is_approved: bool,
    pub ticket_types: Vec<TicketTypePublic>,
    pub total_tickets: i32,
    pub tickets_sold: i32,
    pub created_at: String,
}

pub async fn event_public(
    db: &sqlx::PgPool,
    e: &m::EventInfo,
    scheme: &str,
    host: &str,
) -> EventPublic {
    let vendor = m::vendor_by_id(db, &e.vendor_id)
        .await
        .ok()
        .flatten()
        .map(|v| vendor_public(&v))
        .unwrap_or(VendorPublicOut {
            id: m::dashed(&e.vendor_id),
            brand_name: None,
            business_type: None,
            is_verified: false,
            verification_status: None,
        });
    let mut ticket_types = Vec::new();
    if let Ok(rows) = m::ticket_types_for(db, &e.id).await {
        for t in &rows {
            ticket_types.push(ticket_type_public(db, t).await);
        }
    }
    let total_tickets = if e.is_free {
        e.quantity.unwrap_or(0)
    } else {
        ticket_types.iter().map(|t| t.quantity_available).sum()
    };
    let tickets_sold = m::issued_count(db, &e.id, true).await.unwrap_or(0);
    let event_date = raw(db, "market_place_eventinfo", "event_date", &e.id)
        .await
        .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&e.event_date.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    let created_at = raw(db, "market_place_eventinfo", "created_at", &e.id)
        .await
        .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&e.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    EventPublic {
        id: m::dashed(&e.id),
        vendor,
        event_title: e.event_title.clone(),
        event_description: e.event_description.clone(),
        event_date,
        event_mode: e.event_mode.clone(),
        event_location: e.event_location.clone(),
        meeting_link: e.meeting_link.clone(),
        hosted_by: e.hosted_by.clone(),
        category: e.category.clone(),
        is_free: e.is_free,
        quantity: e.quantity,
        event_banner: if e.event_banner.is_empty() { None } else { Some(absolute(scheme, host, &e.event_banner)) },
        ticket_image: e.ticket_image.as_ref().filter(|s| !s.is_empty()).map(|s| absolute(scheme, host, s)),
        is_approved: e.is_approved,
        ticket_types,
        total_tickets,
        tickets_sold,
        created_at,
    }
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct IssuedTicketOut {
    pub id: String,
    pub ticket_type: Option<TicketTypePublic>,
    pub event_title: String,
    pub event_date: String,
    pub event_location: Option<String>,
    pub event_banner: Option<String>,
    pub vendor_name: Option<String>,
    pub is_free: bool,
    pub owner_name: String,
    pub owner_email: String,
    pub qr_code: String,
    pub status: String,
    pub created_at: String,
}

pub async fn issued_ticket_out(
    db: &sqlx::PgPool,
    t: &m::IssuedTicket,
    scheme: &str,
    host: &str,
) -> IssuedTicketOut {
    let event = m::event_by_id(db, &t.event_id).await.ok().flatten();
    let (event_title, event_date_raw, event_location, event_banner, vendor_name, is_free) =
        match &event {
            Some(e) => {
                let date = raw(db, "market_place_eventinfo", "event_date", &e.id).await.unwrap_or_else(|| e.event_date.format("%Y-%m-%d %H:%M:%S%.f").to_string());
                let vendor_name = m::vendor_by_id(db, &e.vendor_id).await.ok().flatten().and_then(|v| v.brand_name);
                (
                    e.event_title.clone(),
                    date,
                    e.event_location.clone(),
                    if e.event_banner.is_empty() { None } else { Some(absolute(scheme, host, &e.event_banner)) },
                    vendor_name,
                    e.is_free,
                )
            }
            None => (String::new(), String::new(), None, None, None, false),
        };
    let ticket_type = match &t.ticket_type_id {
        Some(tt_id) => {
            let row: Option<m::TicketType> = sqlx::query_as(&format!("SELECT {} FROM market_place_tickettype WHERE id = CAST($1 AS UUID)", m::TICKET_TYPE_COLS))
                .bind(tt_id)
                .fetch_optional(db)
                .await
                .ok()
                .flatten();
            match row {
                Some(tt) => Some(ticket_type_public(db, &tt).await),
                None => None,
            }
        }
        None => None,
    };
    let created_at = raw(db, "market_place_issuedticket", "created_at", &t.id)
        .await
        .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&t.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    IssuedTicketOut {
        id: m::dashed(&t.id),
        ticket_type,
        event_title,
        event_date: if event_date_raw.is_empty() { event_date_raw } else { format_created_at_lagos(&event_date_raw) },
        event_location,
        event_banner,
        vendor_name,
        is_free,
        owner_name: t.owner_name.clone(),
        owner_email: t.owner_email.clone(),
        qr_code: t.qr_code.clone(),
        status: t.status.clone(),
        created_at,
    }
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct TicketListOut {
    pub id: String,
    pub event_title: String,
    pub event_date: String,
    pub event_location: Option<String>,
    pub event_banner: Option<String>,
    pub is_free: bool,
    pub ticket_type_name: String,
    pub ticket_type_price: String,
    pub owner_name: String,
    pub owner_email: String,
    pub status: String,
    pub vendor_name: Option<String>,
    pub created_at: String,
    pub transferred_at: Option<String>,
    pub canceled_at: Option<String>,
}

pub async fn ticket_list_out(
    db: &sqlx::PgPool,
    t: &m::IssuedTicket,
    scheme: &str,
    host: &str,
) -> TicketListOut {
    let base = issued_ticket_out(db, t, scheme, host).await;
    let (type_name, type_price) = match &base.ticket_type {
        Some(tt) if !base.is_free => (tt.name.clone(), tt.price.clone()),
        _ => ("Free Entry".to_string(), "0.00".to_string()),
    };
    let transferred_at = raw(db, "market_place_issuedticket", "transferred_at", &t.id)
        .await
                .map(|r| format_created_at_lagos(&r));
    let canceled_at = raw(db, "market_place_issuedticket", "canceled_at", &t.id)
        .await
                .map(|r| format_created_at_lagos(&r));
    TicketListOut {
        id: base.id,
        event_title: base.event_title,
        event_date: base.event_date,
        event_location: base.event_location,
        event_banner: base.event_banner,
        is_free: base.is_free,
        ticket_type_name: type_name,
        ticket_type_price: type_price,
        owner_name: base.owner_name,
        owner_email: base.owner_email,
        status: base.status,
        vendor_name: base.vendor_name,
        created_at: base.created_at,
        transferred_at,
        canceled_at,
    }
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct ActionStatus {
    pub allowed: bool,
    pub message: String,
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct RefundInfo {
    pub refund_amount: f64,
    pub canceled_at: Option<String>,
    pub reason: Option<String>,
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct TicketDetailOut {
    pub id: String,
    pub event: EventPublic,
    pub ticket_type: Option<TicketTypePublic>,
    pub owner_name: String,
    pub owner_email: String,
    pub qr_code: String,
    pub qr_code_base64: Option<String>,
    pub qr_code_url: Option<String>,
    pub status: String,
    pub purchased_by_email: Option<String>,
    pub transferred_to: Option<String>,
    pub transferred_at: Option<String>,
    pub transfer_count: i32,
    pub canceled_at: Option<String>,
    pub refund_amount: Option<String>,
    pub cancellation_reason: Option<String>,
    pub scanned_at: Option<String>,
    pub scanned_by_email: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub can_transfer: ActionStatus,
    pub can_cancel: ActionStatus,
    pub refund_info: Option<RefundInfo>,
}

/// Mirror of `IssuedTicket.can_transfer()`.
pub fn transfer_status(ticket_status: &str, transfer_count: i32, event_date_utc_raw: &str, now_ts: i64) -> ActionStatus {
    if ticket_status != "upcoming" {
        return ActionStatus { allowed: false, message: "Only upcoming tickets can be transferred".to_string() };
    }
    if transfer_count >= 3 {
        return ActionStatus { allowed: false, message: "Maximum transfer limit (3) reached".to_string() };
    }
    let event_ts = crate::time::parse_stored_dt(event_date_utc_raw)
        .map(|dt| dt.and_utc().timestamp())
        .unwrap_or(i64::MAX);
    if event_ts - now_ts < 6 * 3600 {
        return ActionStatus { allowed: false, message: "Cannot transfer tickets within 6 hours of event start".to_string() };
    }
    ActionStatus { allowed: true, message: "Transfer allowed".to_string() }
}

/// Mirror of `IssuedTicket.can_cancel()`; returns (allowed, refund_cents, message).
pub fn cancel_status(
    ticket_status: &str,
    has_paid_type: bool,
    is_free_event: bool,
    price_cents: i64,
    event_date_utc_raw: &str,
    now_ts: i64,
) -> (bool, i64, String) {
    if ticket_status != "upcoming" {
        return (false, 0, "Only upcoming tickets can be canceled".to_string());
    }
    if !has_paid_type || is_free_event {
        return (false, 0, "Free tickets cannot be canceled".to_string());
    }
    let event_ts = crate::time::parse_stored_dt(event_date_utc_raw)
        .map(|dt| dt.and_utc().timestamp())
        .unwrap_or(i64::MAX);
    let days = (event_ts - now_ts) / 86400;
    if days > 7 {
        (true, price_cents, "100% refund".to_string())
    } else if days >= 3 {
        (true, price_cents / 2, "50% refund".to_string())
    } else {
        (false, 0, "No refunds within 3 days of event".to_string())
    }
}

pub async fn ticket_detail_out(
    db: &sqlx::PgPool,
    media_root: &str,
    t: &m::IssuedTicket,
    scheme: &str,
    host: &str,
    now_ts: i64,
) -> TicketDetailOut {
    let base = issued_ticket_out(db, t, scheme, host).await;
    let event_row = m::event_by_id(db, &t.event_id).await.ok().flatten();
    let event = match event_row {
        Some(e) => event_public(db, &e, scheme, host).await,
        None => EventPublic {
            id: m::dashed(&t.event_id),
            vendor: VendorPublicOut { id: String::new(), brand_name: None, business_type: None, is_verified: false, verification_status: None },
            event_title: base.event_title.clone(),
            event_description: None,
            event_date: base.event_date.clone(),
            event_mode: String::new(),
            event_location: base.event_location.clone(),
            meeting_link: None,
            hosted_by: String::new(),
            category: String::new(),
            is_free: base.is_free,
            quantity: None,
            event_banner: base.event_banner.clone(),
            ticket_image: None,
            is_approved: false,
            ticket_types: vec![],
            total_tickets: 0,
            tickets_sold: 0,
            created_at: String::new(),
        },
    };
    let event_date_raw = m::raw_event_date(db, &t.event_id).await.ok().flatten().unwrap_or_default();
    let price_cents = base.ticket_type.as_ref().and_then(|tt| crate::wallet::models::parse_cents(&tt.price).ok()).unwrap_or(0);
    let can_transfer = transfer_status(&t.status, t.transfer_count, &event_date_raw, now_ts);
    let (can_cancel, _, cancel_msg) = cancel_status(&t.status, t.ticket_type_id.is_some(), base.is_free, price_cents, &event_date_raw, now_ts);
    let purchased_by_email = match t.purchased_by_id {
        Some(uid) => m::profile_email(db, uid).await.ok().flatten(),
        None => None,
    };
    let scanned_by_email = match t.scanned_by_id {
        Some(uid) => m::profile_email(db, uid).await.ok().flatten(),
        None => None,
    };
    let opt_lagos = |col: &'static str| {
        let id_hex = t.id.clone();
        async move {
            raw(db, "market_place_issuedticket", col, &id_hex).await.map(|r| format_created_at_lagos(&r))
        }
    };
    let transferred_at = opt_lagos("transferred_at").await;
    let canceled_at = opt_lagos("canceled_at").await;
    let scanned_at = opt_lagos("scanned_at").await;
    let updated_at = raw(db, "market_place_issuedticket", "updated_at", &t.id)
        .await
                .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| base.created_at.clone());
    let (qr_code_base64, qr_code_url) = match &t.qr_code_image {
        Some(stored) if !stored.is_empty() => {
            let path = std::path::Path::new(media_root).join(stored);
            let b64 = tokio::fs::read(&path).await.ok().map(|b| {
                format!(
                    "data:image/png;base64,{}",
                    base64::engine::general_purpose::STANDARD.encode(&b)
                )
            });
            (b64, Some(absolute(scheme, host, stored)))
        }
        _ => (None, None),
    };
    let refund_amount = t.refund_amount.as_ref().map(|r| dec2(r));
    let refund_info = if t.status == "canceled" {
        if let Some(ref amt) = refund_amount {
            Some(RefundInfo {
                refund_amount: amt.parse::<f64>().unwrap_or(0.0),
                canceled_at: canceled_at.clone(),
                reason: t.cancellation_reason.clone(),
            })
        } else {
            None
        }
    } else {
        None
    };
    TicketDetailOut {
        id: base.id,
        event,
        ticket_type: base.ticket_type,
        owner_name: base.owner_name,
        owner_email: base.owner_email,
        qr_code: base.qr_code,
        qr_code_base64,
        qr_code_url,
        status: base.status,
        purchased_by_email,
        transferred_to: t.transferred_to.clone(),
        transferred_at,
        transfer_count: t.transfer_count,
        canceled_at,
        refund_amount,
        cancellation_reason: t.cancellation_reason.clone(),
        scanned_at,
        scanned_by_email,
        created_at: base.created_at,
        updated_at,
        can_transfer,
        can_cancel: ActionStatus { allowed: can_cancel, message: cancel_msg },
        refund_info,
    }
}

#[derive(Debug, Serialize, ToSchema, Clone)]
pub struct EventWithdrawalPublic {
    pub id: String,
    pub event: String,
    pub amount: String,
    pub platform_fee: String,
    pub amount_credited: String,
    pub status: String,
    pub payment_reference: Option<String>,
    pub created_at: String,
    pub completed_at: Option<String>,
}

pub async fn withdrawal_public(db: &sqlx::PgPool, w: &m::EventWithdrawal) -> EventWithdrawalPublic {
    let created_at = raw(db, "market_place_eventwithdrawal", "created_at", &w.id)
        .await
                .map(|r| format_created_at_lagos(&r))
        .unwrap_or_else(|| format_created_at_lagos(&w.created_at.format("%Y-%m-%d %H:%M:%S%.f").to_string()));
    let completed_at = raw(db, "market_place_eventwithdrawal", "completed_at", &w.id)
        .await
                .map(|r| format_created_at_lagos(&r));
    EventWithdrawalPublic {
        id: m::dashed(&w.id),
        event: m::dashed(&w.event_id),
        amount: dec2(&w.amount),
        platform_fee: dec2(&w.platform_fee),
        amount_credited: dec2(&w.amount_credited),
        status: w.status.clone(),
        payment_reference: w.payment_reference.clone(),
        created_at,
        completed_at,
    }
}
