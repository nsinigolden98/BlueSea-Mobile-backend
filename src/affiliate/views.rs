//! Affiliate endpoints. Mirrors `affiliate/views.py`:
//! apply (update-or-create), status, links (list + get-or-create),
//! attribution, dashboard and sales (with payable sweep), payout.

use axum::{Json, extract::State, http::{HeaderMap, StatusCode}};
use serde_json::{Value, json};

use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;
use crate::transactions::serializers::format_created_at_lagos;
use crate::wallet::models::dec2;

use super::models as affiliate_models;
use super::serializers as affiliate_serializers;
use super::utils as affiliate_utils;

type Resp = (StatusCode, Json<Value>);

fn not_found_detail() -> Resp {
    (
        StatusCode::NOT_FOUND,
        Json(json!({"detail": "Not found."})),
    )
}

async fn profile_or_404(s: &AppState, user_id: i64) -> Result<affiliate_models::AffiliateProfileRow, Resp> {
    match affiliate_models::profile_for_user(&s.db, user_id).await {
        Ok(Some(p)) => Ok(p),
        Ok(None) => Err(not_found_detail()),
        Err(_) => Err(not_found_detail()),
    }
}

async fn status_public(
    s: &AppState,
    p: &affiliate_models::AffiliateProfileRow,
) -> Value {
    let created: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(created_at AS TEXT) FROM affiliate_affiliateprofile WHERE id = $1",
    )
    .bind(p.id)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    serde_json::to_value(&affiliate_serializers::AffiliateStatusPublic::from_row(
        p,
        &created.map(|(c,)| c).unwrap_or_default(),
    ))
    .unwrap_or(Value::Null)
}

#[utoipa::path(
    post,
    path = "/affiliate/apply/",
    tag = "Affiliate",
    summary = "Apply to become an affiliate",
    description = "Submit an affiliate application. Name must be unique alphanumeric; agreement must be true.",
    request_body = crate::affiliate::serializers::AffiliateApplyBody,
    responses((status = 201, description = "Application saved"), (status = 400, description = "Invalid")),
    security(("bearer" = [])),
)]
pub async fn apply(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let params = match affiliate_serializers::validate_apply(&body) {
        Ok(p) => p,
        Err(e) => return Ok((StatusCode::BAD_REQUEST, Json(e))),
    };
    if affiliate_models::name_taken_by_other(&s.db, &params.affiliate_name, user.id).await? {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"affiliate_name": ["This affiliate name is already taken. Please choose another one."]})),
        ));
    }

    let now = crate::time::now_str();
    let existing = affiliate_models::profile_for_user(&s.db, user.id).await?;
    if let Some(p) = existing {
        sqlx::query(
            "UPDATE affiliate_affiliateprofile SET affiliate_name = $1, facebook = $2, instagram = $3,
             twitter = $4, tiktok = $5, agreement_accepted = $6, updated_at = $7 WHERE id = $8",
        )
        .bind(&params.affiliate_name)
        .bind(params.facebook.as_deref())
        .bind(params.instagram.as_deref())
        .bind(params.twitter.as_deref())
        .bind(params.tiktok.as_deref())
        .bind(params.agreement)
        .bind(crate::time::Ts(&now))
        .bind(p.id)
        .execute(&s.db)
        .await?;
        if p.status == "rejected" {
            let _ = sqlx::query("UPDATE affiliate_affiliateprofile SET status = 'pending' WHERE id = $1")
                .bind(p.id)
                .execute(&s.db)
                .await;
        }
    } else {
        sqlx::query(
            "INSERT INTO affiliate_affiliateprofile (status, commission_rate, facebook, instagram, twitter, tiktok,
                    agreement_accepted, rejected_reason, created_at, updated_at, user_id, affiliate_name)
             VALUES ('pending', '2.00', $1, $2, $3, $4, $5, NULL, $6, $7, $8, $9)",
        )
        .bind(params.facebook.as_deref())
        .bind(params.instagram.as_deref())
        .bind(params.twitter.as_deref())
        .bind(params.tiktok.as_deref())
        .bind(params.agreement)
        .bind(crate::time::Ts(&now))
        .bind(crate::time::Ts(&now))
        .bind(user.id)
        .bind(&params.affiliate_name)
        .execute(&s.db)
        .await?;
    }
    let profile = affiliate_models::profile_for_user(&s.db, user.id)
        .await?
        .ok_or_else(|| AppError::internal("profile vanished"))?;
    Ok((StatusCode::CREATED, Json(status_public(&s, &profile).await)))
}

#[utoipa::path(
    get,
    path = "/affiliate/status/",
    tag = "Affiliate",
    summary = "Get my affiliate status",
    description = "Return the affiliate application status and settings for the authenticated user.",
    responses((status = 200, description = "Status"), (status = 404, description = "No profile")),
    security(("bearer" = [])),
)]
pub async fn status(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    match profile_or_404(&s, user.id).await {
        Ok(p) => Ok((StatusCode::OK, Json(status_public(&s, &p).await))),
        Err(e) => Ok(e),
    }
}

async fn link_public(
    s: &AppState,
    link_id: i64,
    commission_raw: &str,
    clicks: i64,
    is_active: bool,
    event_hex: &str,
    created_raw: &str,
) -> Value {
    let title: Option<(String,)> =
        sqlx::query_as("SELECT event_title FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)")
            .bind(event_hex)
            .fetch_optional(&s.db)
            .await
            .unwrap_or(None);
    let name: Option<(String,)> = sqlx::query_as(
        "SELECT affiliate_name FROM affiliate_affiliateprofile WHERE id =
         (SELECT affiliate_id FROM affiliate_affiliatelink WHERE id = $1)",
    )
    .bind(link_id)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    let dashed = crate::loyalty_market::serializers::dashed_uuid(event_hex);
    json!({
        "id": link_id,
        "event": dashed,
        "event_title": title.map(|(t,)| t),
        "commission_rate": dec2(commission_raw),
        "clicks": clicks,
        "is_active": is_active,
        "link": format!("/events/{dashed}/?affiliate={}", name.map(|(n,)| n).unwrap_or_default()),
        "created_at": format_created_at_lagos(created_raw),
    })
}

#[utoipa::path(
    get,
    path = "/affiliate/links/",
    tag = "Affiliate",
    summary = "List my affiliate links",
    description = "List all affiliate links generated by the authenticated user.",
    responses((status = 200, description = "Link list"), (status = 404, description = "No profile")),
    security(("bearer" = [])),
)]
pub async fn links_list(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let profile = match profile_or_404(&s, user.id).await {
        Ok(p) => p,
        Err(e) => return Ok(e),
    };
    let rows: Vec<(i64, String, i64, bool, String, String)> = sqlx::query_as(
        "SELECT id, CAST(commission_rate AS TEXT), clicks, is_active, event_id, CAST(created_at AS TEXT)
         FROM affiliate_affiliatelink WHERE affiliate_id = $1 ORDER BY created_at DESC",
    )
    .bind(profile.id)
    .fetch_all(&s.db)
    .await?;
    let mut out = Vec::new();
    for (id, rate, clicks, active, event_hex, created) in rows {
        out.push(link_public(&s, id, &rate, clicks, active, &event_hex, &created).await);
    }
    Ok((StatusCode::OK, Json(Value::Array(out))))
}

#[utoipa::path(
    post,
    path = "/affiliate/links/",
    tag = "Affiliate",
    summary = "Generate an affiliate link for an event",
    description = "Create a shareable link for an approved event. Requires an approved affiliate profile.",
    request_body = crate::affiliate::serializers::AffiliateLinkCreateBody,
    responses(
        (status = 200, description = "Link"),
        (status = 400, description = "Missing or unapproved event"),
        (status = 403, description = "Affiliate not approved"),
        (status = 404, description = "No profile or event"),
    ),
    security(("bearer" = [])),
)]
pub async fn links_create(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let profile = match profile_or_404(&s, user.id).await {
        Ok(p) => p,
        Err(e) => return Ok(e),
    };
    if profile.status != "approved" {
        return Ok((
            StatusCode::FORBIDDEN,
            Json(json!({"error": "Your affiliate application has not been approved yet."})),
        ));
    }
    let event_id = body.get("event_id").and_then(|v| v.as_str()).unwrap_or("");
    if event_id.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "event_id is required"})),
        ));
    }
    let Some(hex) = crate::market_place::models::norm_id(event_id) else {
        return Ok(not_found_detail());
    };
    let event = match affiliate_models::event_by_id(&s.db, &hex).await? {
        Some(e) => e,
        None => return Ok(not_found_detail()),
    };
    if !event.is_approved {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "This event is not yet approved for ticket sales"})),
        ));
    }
    let existing: Option<(i64, String, i64, bool, String)> = sqlx::query_as(
        "SELECT id, CAST(commission_rate AS TEXT), clicks, is_active, CAST(created_at AS TEXT)
         FROM affiliate_affiliatelink WHERE affiliate_id = $1 AND event_id = CAST($2 AS UUID)",
    )
    .bind(profile.id)
    .bind(&event.id)
    .fetch_optional(&s.db)
    .await?;
    let (link_id, created) = match existing {
        Some((id, _, _, _, _)) => (id, false),
        None => {
            let now = crate::time::now_str();
            let res = sqlx::query_as::<_, (i64,)>(
                "INSERT INTO affiliate_affiliatelink (commission_rate, clicks, is_active, created_at, event_id, affiliate_id)
                 VALUES ($1, 0, TRUE, $2, CAST($3 AS UUID), $4) RETURNING id",
            )
            .bind(&profile.commission_rate)
            .bind(crate::time::Ts(&now))
            .bind(&event.id)
            .bind(profile.id)
            .fetch_one(&s.db)
            .await?;
            (res.0, true)
        }
    };
    let row: Option<(String, i64, bool, String)> = sqlx::query_as(
        "SELECT CAST(commission_rate AS TEXT), clicks, is_active, CAST(created_at AS TEXT)
         FROM affiliate_affiliatelink WHERE id = $1",
    )
    .bind(link_id)
    .fetch_optional(&s.db)
    .await?;
    let Some((rate, clicks, active, created_raw)) = row else {
        return Ok(not_found_detail());
    };
    let mut v = link_public(&s, link_id, &rate, clicks, active, &event.id, &created_raw).await;
    if let Value::Object(map) = &mut v {
        map.insert("created".to_string(), Value::Bool(created));
    }
    Ok((StatusCode::OK, Json(v)))
}

#[utoipa::path(
    post,
    path = "/affiliate/attribution/",
    tag = "Affiliate",
    summary = "Record affiliate link attribution",
    description = "Record that the authenticated user opened an event via an affiliate link.",
    request_body = crate::affiliate::serializers::AffiliateAttributionBody,
    responses(
        (status = 200, description = "Recorded"),
        (status = 400, description = "Missing fields or invalid link"),
        (status = 404, description = "No event"),
    ),
    security(("bearer" = [])),
)]
pub async fn attribution(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let event_id = body.get("event_id").and_then(|v| v.as_str()).unwrap_or("");
    let name = body.get("affiliate_username").and_then(|v| v.as_str()).unwrap_or("");
    if event_id.is_empty() || name.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "event_id and affiliate_username are required"})),
        ));
    }
    let Some(hex) = crate::market_place::models::norm_id(event_id) else {
        return Ok(not_found_detail());
    };
    let event = match affiliate_models::event_by_id(&s.db, &hex).await? {
        Some(e) => e,
        None => return Ok(not_found_detail()),
    };
    match affiliate_utils::record_attribution(&s.db, user.id, &event, name).await? {
        Some(att) => Ok((
            StatusCode::OK,
            Json(json!({
                "success": true,
                "status": att.status,
                "event_id": crate::loyalty_market::serializers::dashed_uuid(&event.id),
                "affiliate_username": name,
                "message": if att.status == "pending" {
                    "You will be attributed to this affiliate when you purchase tickets."
                } else {
                    "This event is already attributed."
                },
            })),
        )),
        None => Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Invalid or inactive affiliate link for this event"})),
        )),
    }
}

async fn sale_public(
    s: &AppState,
    sale_id: i64,
    status: &str,
    tickets: i64,
    gross_raw: &str,
    rate_raw: &str,
    commission_raw: &str,
    created_raw: &str,
    payable_raw: Option<&str>,
    paid_raw: Option<&str>,
    affiliate_id: i64,
    buyer_id: i64,
    event_hex: &str,
) -> Value {
    let aff_name: Option<(String,)> = sqlx::query_as(
        "SELECT affiliate_name FROM affiliate_affiliateprofile WHERE id = $1",
    )
    .bind(affiliate_id)
    .fetch_optional(&s.db)
    .await
    .unwrap_or(None);
    let buyer_email: Option<(String,)> =
        sqlx::query_as("SELECT email FROM accounts_profile WHERE id = $1")
            .bind(buyer_id)
            .fetch_optional(&s.db)
            .await
            .unwrap_or(None);
    let event_title: Option<(String,)> =
        sqlx::query_as("SELECT event_title FROM market_place_eventinfo WHERE id = CAST($1 AS UUID)")
            .bind(event_hex)
            .fetch_optional(&s.db)
            .await
            .unwrap_or(None);
    let _ = sale_id;
    json!({
        "id": sale_id,
        "affiliate_name": aff_name.map(|(n,)| n),
        "event": crate::loyalty_market::serializers::dashed_uuid(event_hex),
        "event_title": event_title.map(|(t,)| t),
        "buyer": buyer_id,
        "buyer_email": buyer_email.map(|(e,)| e),
        "ticket_count": tickets,
        "gross_amount": dec2(gross_raw),
        "commission_rate": dec2(rate_raw),
        "commission_amount": dec2(commission_raw),
        "status": status,
        "created_at": format_created_at_lagos(created_raw),
        "payable_at": payable_raw.map(format_created_at_lagos),
        "paid_at": paid_raw.map(format_created_at_lagos),
    })
}

#[utoipa::path(
    get,
    path = "/affiliate/dashboard/",
    tag = "Affiliate",
    summary = "Get affiliate dashboard",
    description = "Return click totals and commission amounts grouped by status. Runs the payable sweep first.",
    responses((status = 200, description = "Dashboard"), (status = 404, description = "No profile")),
    security(("bearer" = [])),
)]
pub async fn dashboard(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let profile = match profile_or_404(&s, user.id).await {
        Ok(p) => p,
        Err(e) => return Ok(e),
    };
    let now = crate::time::now_str();
    let _ = affiliate_utils::sweep_payable(&s.db, Some(profile.id), &now).await;
    let clicks: Option<(Option<i64>,)> = sqlx::query_as(
        "SELECT SUM(clicks) FROM affiliate_affiliatelink WHERE affiliate_id = $1",
    )
    .bind(profile.id)
    .fetch_optional(&s.db)
    .await?;
    let counts: Option<(i64, i64, i64, i64, i64, i64, Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT COUNT(*),
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'payable' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'revoked' THEN 1 ELSE 0 END),
                CAST(SUM(CASE WHEN status = 'pending' THEN commission_amount ELSE 0 END) AS TEXT),
                CAST(SUM(CASE WHEN status = 'payable' THEN commission_amount ELSE 0 END) AS TEXT),
                CAST(SUM(CASE WHEN status = 'paid' THEN commission_amount ELSE 0 END) AS TEXT)
         FROM affiliate_affiliatesale WHERE affiliate_id = $1",
    )
    .bind(profile.id)
    .fetch_optional(&s.db)
    .await?;
    let (total, pending, success, payable, paid, revoked, pending_amt, payable_amt, paid_amt) =
        counts.unwrap_or((0, 0, 0, 0, 0, 0, None, None, None));
    Ok((
        StatusCode::OK,
        Json(json!({
            "total_clicks": clicks.and_then(|(c,)| c).unwrap_or(0),
            "total_sales": total,
            "pending_count": pending,
            "success_count": success,
            "payable_count": payable,
            "paid_count": paid,
            "revoked_count": revoked,
            "pending_amount": pending_amt.map(|a| dec2(&a)).unwrap_or_else(|| "0.00".to_string()),
            "payable_amount": payable_amt.map(|a| dec2(&a)).unwrap_or_else(|| "0.00".to_string()),
            "paid_amount": paid_amt.map(|a| dec2(&a)).unwrap_or_else(|| "0.00".to_string()),
        })),
    ))
}

#[utoipa::path(
    post,
    path = "/affiliate/payout/",
    tag = "Affiliate",
    summary = "Request affiliate payout",
    description = "Credit all payable commissions to the authenticated affiliate's wallet. Runs the payable sweep first.",
    responses(
        (status = 200, description = "Paid out or nothing payable"),
        (status = 403, description = "Affiliate not approved"),
        (status = 404, description = "No profile"),
    ),
    security(("bearer" = [])),
)]
pub async fn payout(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let profile = match profile_or_404(&s, user.id).await {
        Ok(p) => p,
        Err(e) => return Ok(e),
    };
    if profile.status != "approved" {
        return Ok((
            StatusCode::FORBIDDEN,
            Json(json!({"error": "Your affiliate application has not been approved yet."})),
        ));
    }
    let (paid, total, reference) =
        affiliate_utils::pay_out(&s, profile.id, user.id).await?;
    let total_dec: rust_decimal::Decimal =
        total.parse().unwrap_or(rust_decimal::Decimal::ZERO);
    if total_dec <= rust_decimal::Decimal::ZERO {
        return Ok((
            StatusCode::OK,
            Json(json!({
                "message": "No payable commissions to pay out.",
                "amount_paid": "0.00",
            })),
        ));
    }
    let balance: Option<(String,)> = sqlx::query_as(
        "SELECT CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = $1",
    )
    .bind(user.id)
    .fetch_optional(&s.db)
    .await?;
    Ok((
        StatusCode::OK,
        Json(json!({
            "success": true,
            "message": format!("{} commission(s) paid out.", paid.len()),
            "amount_paid": total,
            "wallet_balance": balance.map(|(b,)| b).unwrap_or_default(),
            "reference": reference,
        })),
    ))
}
#[utoipa::path(
    get,
    path = "/affiliate/sales/",
    tag = "Affiliate",
    summary = "List my affiliate commissions",
    description = "List commission records for the authenticated affiliate. Runs the payable sweep first.",
    responses((status = 200, description = "Sale list"), (status = 404, description = "No profile")),
    security(("bearer" = [])),
)]
pub async fn sales(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;
    let profile = match profile_or_404(&s, user.id).await {
        Ok(p) => p,
        Err(e) => return Ok(e),
    };
    let now = crate::time::now_str();
    let _ = affiliate_utils::sweep_payable(&s.db, Some(profile.id), &now).await;
    let rows: Vec<(
        i64, i64, String, String, String, String, String, Option<String>, Option<String>,
        i64, i64, String,
    )> = sqlx::query_as(
        "SELECT id, ticket_count, CAST(gross_amount AS TEXT), CAST(commission_rate AS TEXT),
                CAST(commission_amount AS TEXT), status, CAST(created_at AS TEXT),
                CAST(payable_at AS TEXT), CAST(paid_at AS TEXT),
                affiliate_id, buyer_id, event_id
         FROM affiliate_affiliatesale WHERE affiliate_id = $1 ORDER BY created_at DESC",
    )
    .bind(profile.id)
    .fetch_all(&s.db)
    .await?;
    let mut out = Vec::new();
    for (
        id, tickets, gross, rate, commission, status, created,
        payable, paid, aid, buyer, event_hex,
    ) in rows
    {
        out.push(
            sale_public(
                &s, id, &status, tickets, &gross, &rate, &commission, &created,
                payable.as_deref(), paid.as_deref(), aid, buyer, &event_hex,
            )
            .await,
        );
    }
    Ok((StatusCode::OK, Json(Value::Array(out))))
}
