//! Group payments. Mirrors `payments/views.py::GroupPaymentViews` (PIN gate,
//! admin check, exact-decimal splits, per-member debits, sync VTU call,
//! completion or reversal) and `GroupPaymentHistory` (member-scoped list).

use std::collections::HashMap;

use axum::{Json, extract::{State}, http::{HeaderMap, StatusCode}};
use rust_decimal::Decimal;
use serde_json::{Value, json};

use crate::error::AppError;
use crate::notifications::utils as notify;
use crate::payments::models as pay_models;
use crate::payments::plans;
use crate::payments::serializers::{ContributionPublic, GroupPaymentPublic};
use crate::payments::vtpass;
use crate::state::AppState;
use crate::transactions::serializers::{format_created_at_lagos, format_naive_lagos};
use crate::wallet::models as wallet_models;

type Resp = (StatusCode, Json<Value>);

fn coerce_decimal(v: &Value) -> Option<Decimal> {
    match v {
        Value::String(s) => s.trim().parse::<Decimal>().ok(),
        Value::Number(n) => n.to_string().parse::<Decimal>().ok(),
        _ => None,
    }
}

/// Django `str(Decimal)` preserves scale ("1000.00" stays "1000.00").

struct MemberCtx {
    member_id: i64,
    user_id: i64,
    email: String,
    other_names: String,
    wallet_id: Option<i64>,
    balance: Decimal,
}

async fn member_contexts(
    s: &AppState,
    members: &[pay_models::GroupMemberRow],
) -> Result<Vec<MemberCtx>, AppError> {
    let mut out = Vec::new();
    for m in members {
        let prof: Option<(String, String)> = sqlx::query_as(
            "SELECT other_names, email FROM accounts_profile WHERE id = ?",
        )
        .bind(m.user_id)
        .fetch_optional(&s.db)
        .await?;
        let Some((other_names, email)) = prof else {
            continue;
        };
        let w: Option<(i64, String)> = sqlx::query_as(
            "SELECT id, CAST(balance AS TEXT) FROM wallet_wallet WHERE user_id = ?",
        )
        .bind(m.user_id)
        .fetch_optional(&s.db)
        .await?;
        let (wallet_id, balance) = match w {
            Some((id, raw)) => (
                Some(id),
                raw.parse::<Decimal>().unwrap_or(Decimal::ZERO),
            ),
            None => (None, Decimal::ZERO),
        };
        out.push(MemberCtx {
            member_id: m.id,
            user_id: m.user_id,
            email,
            other_names,
            wallet_id,
            balance,
        });
    }
    Ok(out)
}

#[utoipa::path(
    post,
    path = "/payments/group-payment/",
    tag = "Payments",
    summary = "Create group payment",
    description = "Initiate a payment on behalf of a group; splits the total across members. Wallet debited on success.",
    request_body = crate::payments::serializers::GroupPaymentBody,
    responses(
        (status = 200, description = "Group payment completed"),
        (status = 400, description = "Validation, funds or VTU failure"),
        (status = 403, description = "Only group admins can initiate payments"),
    ),
    security(("bearer" = [])),
)]
pub async fn create_group_payment(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Resp, AppError> {
    // PIN gate, group dialect (bare {"error"}).
    let user = match crate::payments::views::common::pin_gate(&s, headers, &body, false).await {
        Ok(u) => u,
        Err(e) => return Ok(e),
    };

    let group_id = body
        .get("group_id")
        .and_then(|v| match v {
            Value::String(s) => Some(s.clone()),
            Value::Number(n) => Some(n.to_string()),
            _ => None,
        })
        .unwrap_or_default();
    let payment_type = body
        .get("payment_type")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let total = body.get("total_amount").and_then(coerce_decimal);
    let details = body.get("service_details").cloned().unwrap_or(Value::Null);
    let split_type = body
        .get("split_type")
        .and_then(|v| v.as_str())
        .unwrap_or("equal");
    let custom_splits = body.get("custom_splits").cloned().unwrap_or(Value::Null);

    let Some(total) = total else {
        return Ok((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"success": false, "error": "Payment failed: Invalid total_amount"})),
        ));
    };

    // 404 like get_object_or_404 (DRF {"detail"} shape).
    let group: Option<(String, String)> = pay_models::group_by_id(&s.db, &group_id).await?;
    let Some((group_name, group_status)) = group else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"detail": "Not found."})),
        ));
    };

    if !pay_models::is_group_admin(&s.db, &group_id, user.id).await? {
        return Ok((
            StatusCode::FORBIDDEN,
            Json(json!({"error": "Only group admins can initiate payments"})),
        ));
    }
    let members = pay_models::group_members(&s.db, &group_id).await?;
    if group_status == "completed" {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "Cannot initiate payment for a completed group"})),
        ));
    }
    if members.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "No active members in group"})),
        ));
    }
    let ctxs = member_contexts(&s, &members).await?;

    // Splits (exact decimals, like Django).
    let count = Decimal::from(ctxs.len() as i64);
    let mut shares: HashMap<i64, Decimal> = HashMap::new();
    if split_type == "percentage" {
        for c in &ctxs {
            let pct = custom_splits
                .get(&c.user_id.to_string())
                .and_then(coerce_decimal)
                .unwrap_or(Decimal::ZERO);
            shares.insert(c.member_id, (total * pct) / Decimal::from(100));
        }
    } else {
        for c in &ctxs {
            shares.insert(c.member_id, total / count);
        }
    }

    // All-or-nothing balance pre-check (Django's atomic block rolls back
    // partial debits; sequential debits approximate it).
    for c in &ctxs {
        let share = shares.get(&c.member_id).cloned().unwrap_or(Decimal::ZERO);
        if c.balance < share {
            return Ok((
                StatusCode::BAD_REQUEST,
                Json(json!({"success": false, "error": format!("Insufficient funds for {}", c.email)})),
            ));
        }
    }

    let now = crate::time::now_str();
    let total_stored = total
        .round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointNearestEven);
    let details_json = serde_json::to_string(&details).unwrap_or_else(|_| "null".to_string());
    let payment_id = match pay_models::insert_group_payment(
        &s.db, &group_id, user.id, &payment_type,
        (total_stored * Decimal::from(100))
            .round()
            .to_string()
            .parse::<i64>()
            .unwrap_or(0),
        &details_json, &now,
    )
    .await
    {
        Ok(id) => id,
        Err(e) => {
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Payment failed: {e}")})),
            ))
        }
    };

    // Debit each member + pending contribution + notification.
    // A missing wallet raises into the 500 branch, like Django.
    for c in &ctxs {
        let share = shares.get(&c.member_id).cloned().unwrap_or(Decimal::ZERO);
        let Some(wallet_id) = c.wallet_id else {
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": "Payment failed: missing wallet"})),
            ));
        };
        let unique_ref = format!(
            "GP-{payment_id}-{}-{}",
            c.user_id,
            uuid::Uuid::new_v4().simple().to_string()[..8].to_uppercase()
        );
        if let Err(e) = wallet_models::debit_decimal(
            &s.db, &s.wallet_hub, wallet_id, c.user_id, share,
            &format!("Group payment contribution - {payment_type}"),
            &unique_ref,
        )
        .await
        {
            tracing::error!("group debit failed after pre-check: {e:?}");
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Payment failed: {e:?}. All debits have been reversed.")})),
            ));
        }
        let _ = pay_models::insert_contribution_str(
            &s.db, payment_id, c.member_id, &share.to_string(), "pending", &now,
        )
        .await;
        let _ = notify::contribution_notification(
            &s, c.user_id, &c.email, &c.other_names,
            &share.to_string(), &group_name, &payment_type,
        )
        .await
        .map_err(|e| tracing::warn!("Failed to send notification to {}: {e}", c.email));
    }

    // Sync VTU call.
    let vtu_response = vtu_api_call(&s, &payment_type, &details, &total).await;
    let vtu_response = match vtu_response {
        Ok(r) => r,
        Err(e) => {
            reverse_all(&s, payment_id, &ctxs, &shares, &group_id).await;
            notify_all_failed(&s, &ctxs, &shares, &group_name, &payment_type, &e).await;
            return Ok((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"success": false, "error": format!("Payment failed: {e}. All debits have been reversed.")})),
            ));
        }
    };

    if vtpass_ok(&vtu_response) {
        let vtu_ref = vtu_response
            .get("requestId")
            .and_then(|v| v.as_str())
            .or_else(|| vtu_response.get("reference").and_then(|v| v.as_str()))
            .map(|v| v.to_string());
        let _ = pay_models::set_group_payment_status(&s.db, payment_id, "completed", vtu_ref.as_deref(), &now).await;
        let _ = pay_models::set_group_status(&s.db, &group_id, "completed").await;
        let _ = pay_models::set_contributions_status(&s.db, payment_id, None, "completed").await;
        for c in &ctxs {
            let share = shares.get(&c.member_id).cloned().unwrap_or(Decimal::ZERO);
            let _ = notify::group_payment_success(
                &s, c.user_id, &c.email, &c.other_names,
                &share.to_string(), &group_name, &payment_type,
                vtu_ref.as_deref().unwrap_or(""),
            )
            .await
            .map_err(|e| tracing::warn!("Failed to send success notification: {e}"));
        }
        return Ok((
            StatusCode::OK,
            Json(json!({
                "success": true,
                "message": "Group payment completed successfully",
                "payment_id": payment_id,
                "vtu_reference": vtu_ref,
                "total_amount": total.to_string(),
                "member_contributions": ctxs.iter().map(|c| {
                    let sh = shares.get(&c.member_id).cloned().unwrap_or(Decimal::ZERO);
                    (c.email.clone(), Value::String(sh.to_string()))
                }).collect::<serde_json::Map<String, Value>>(),
            })),
        ));
    }

    // VTU failure: reverse all debits.
    reverse_all(&s, payment_id, &ctxs, &shares, &group_id).await;
    let _ = pay_models::set_group_payment_status(&s.db, payment_id, "failed", None, &now).await;
    let _ = pay_models::set_group_status(&s.db, &group_id, "failed").await;
    Ok((
        StatusCode::BAD_REQUEST,
        Json(json!({
            "success": false,
            "error": format!(
                "VTU service failed: {}. All debits have been reversed.",
                vtu_response.get("response_description").and_then(|v| v.as_str()).unwrap_or("Unknown error")
            ),
            "payment_id": payment_id,
        })),
    ))
}

async fn reverse_all(
    s: &AppState,
    payment_id: i64,
    ctxs: &[MemberCtx],
    shares: &HashMap<i64, Decimal>,
    _group_id: &str,
) {
    for c in ctxs {
        let share = shares.get(&c.member_id).cloned().unwrap_or(Decimal::ZERO);
        if let Some(wallet_id) = c.wallet_id {
            let rev_ref = format!(
                "REV-{payment_id}-{}-{}",
                c.user_id,
                uuid::Uuid::new_v4().simple().to_string()[..8].to_uppercase()
            );
            let _ = wallet_models::credit_decimal(
                &s.db, &s.wallet_hub, wallet_id, c.user_id, share,
                "Reversal - Group payment failed", &rev_ref,
            )
            .await;
        }
        let _ = pay_models::set_contributions_status(&s.db, payment_id, Some(c.member_id), "reversed").await;
    }
}

async fn notify_all_failed(
    s: &AppState,
    ctxs: &[MemberCtx],
    shares: &HashMap<i64, Decimal>,
    group_name: &str,
    payment_type: &str,
    reason: &str,
) {
    for c in ctxs {
        let share = shares.get(&c.member_id).cloned().unwrap_or(Decimal::ZERO);
        let _ = notify::group_payment_failed(
            s, c.user_id, &c.email, &c.other_names,
            &share.to_string(), group_name, payment_type, reason,
        )
        .await
        .map_err(|e| tracing::warn!("Failed to send failure notification: {e}"));
    }
}

fn vtpass_ok(resp: &Value) -> bool {
    resp.get("response_description").and_then(|v| v.as_str()) == Some("TRANSACTION SUCCESSFUL")
}

/// Sync VTU dispatch for a group payment. Mirrors `vtu_api()`.
async fn vtu_api_call(
    s: &AppState,
    payment_type: &str,
    details: &Value,
    total: &Decimal,
) -> Result<Value, String> {
    let request_id = vtpass::generate_reference_id();
    let get = |k: &str| details.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string();
    let total_naira = total.trunc().to_string().parse::<i64>().unwrap_or(0);

    let payload = match payment_type {
        "airtime" => serde_json::json!({
            "request_id": request_id,
            "serviceID": get("network"),
            "amount": total_naira,
            "phone": get("phone_number"),
        }),
        "data" => {
            let net = get("network");
            let plan_id = get("plan_id");
            let dict = match net.as_str() {
                "mtn" => plans::MTN_PLANS,
                "airtel" => plans::AIRTEL_PLANS,
                "glo" => plans::GLO_PLANS,
                "etisalat" => plans::ETISALAT_PLANS,
                _ => return Err(format!("unsupported network {net}")),
            };
            let plan = plans::find_plan(dict, &plan_id)
                .ok_or_else(|| format!("unknown plan {plan_id}"))?;
            serde_json::json!({
                "request_id": request_id,
                "serviceID": format!("{net}-data"),
                "billersCode": get("billersCode"),
                "variation_code": plan.code,
                "amount": plan.price_naira,
                "phone": get("phone_number"),
            })
        }
        "electricity" => serde_json::json!({
            "request_id": request_id,
            "serviceID": get("disco"),
            "billersCode": get("billersCode"),
            "variation_code": get("meter_type"),
            "amount": total_naira,
            "phone": get("phone_number"),
        }),
        "dstv" | "gotv" | "startimes" | "showmax" => {
            let dict = match payment_type {
                "dstv" => plans::DSTV_PLANS,
                "gotv" => plans::GOTV_PLANS,
                "startimes" => plans::STARTIMES_PLANS,
                _ => plans::SHOWMAX_PLANS,
            };
            let plan_id = get("plan_id");
            let plan = plans::find_plan(dict, &plan_id)
                .ok_or_else(|| format!("unknown plan {plan_id}"))?;
            serde_json::json!({
                "request_id": request_id,
                "serviceID": payment_type,
                "billersCode": get("billersCode"),
                "variation_code": plan.code,
                "amount": plan.price_naira,
                "phone": get("phone_number"),
            })
        }
        "jamb" => {
            let exam = get("exam_type");
            let _amount = if exam == "utme-mock" { 7700 } else { 6200 };
            serde_json::json!({
                "request_id": request_id,
                "serviceID": "jamb",
                "variation_code": exam,
                "billersCode": get("billersCode"),
                "phone": get("phone_number"),
            })
        }
        "waec-registration" => serde_json::json!({
            "request_id": request_id,
            "serviceID": "waec-registration",
            "variation_code": "waec-registraion",
            "quantity": 1,
            "phone": get("phone_number"),
        }),
        "waec-result" => serde_json::json!({
            "request_id": request_id,
            "serviceID": "waec",
            "variation_code": "waecdirect",
            "quantity": 1,
            "phone": get("phone_number"),
        }),
        other => return Err(format!("unsupported payment_type {other}")),
    };
    vtpass::top_up(&s.http, &s.config, &payload)
        .await
        .map_err(|e| format!("VTU service failed: {e}"))
}

// ---------- history ----------

#[utoipa::path(
    get,
    path = "/payments/group-payment/history/",
    tag = "Payments",
    summary = "Get group payment history",
    description = "List group payment history for a specific group (via group_id query param) or all groups the user belongs to.",
    params(("group_id" = Option<String>, Query, description = "Filter by specific group ID")),
    responses((status = 200, description = "Payment list"), (status = 403, description = "Not a member of this group")),
    security(("bearer" = [])),
)]
pub async fn group_history(
    State(s): State<AppState>,
    headers: HeaderMap,
    axum::extract::Query(query): axum::extract::Query<HashMap<String, String>>,
) -> Result<Resp, AppError> {
    use crate::auth::extractor::auth_user;

    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::unauthorized("Authentication required"))?;

    let mut rows: Vec<GroupHistoryRow> = Vec::new();
    if let Some(gid) = query.get("group_id") {
        let member: Option<(i64,)> = sqlx::query_as(
            "SELECT id FROM group_payment_groupmember WHERE group_id = ? AND user_id = ?",
        )
        .bind(gid)
        .bind(user.id)
        .fetch_optional(&s.db)
        .await?;
        if member.is_none() {
            return Ok((
                StatusCode::FORBIDDEN,
                Json(json!({"error": "You are not a member of this group"})),
            ));
        }
        rows = sqlx::query_as::<_, GroupHistoryRow>(
            "SELECT id, payment_type, CAST(total_amount AS TEXT), service_details, status,
                    CAST(created_at AS TEXT), CAST(updated_at AS TEXT), group_id, initiated_by_id, vtu_reference
             FROM payments_grouppayment WHERE group_id = ? ORDER BY created_at DESC",
        )
        .bind(gid)
        .fetch_all(&s.db)
        .await?;
    } else {
        let my_groups: Vec<(String,)> =
            sqlx::query_as("SELECT group_id FROM group_payment_groupmember WHERE user_id = ?")
                .bind(user.id)
                .fetch_all(&s.db)
                .await?;
        for (gid,) in my_groups {
            let mut r: Vec<GroupHistoryRow> = sqlx::query_as(
                "SELECT id, payment_type, CAST(total_amount AS TEXT), service_details, status,
                        CAST(created_at AS TEXT), CAST(updated_at AS TEXT), group_id, initiated_by_id, vtu_reference
                 FROM payments_grouppayment WHERE group_id = ? ORDER BY created_at DESC",
            )
            .bind(&gid)
            .fetch_all(&s.db)
            .await?;
            rows.append(&mut r);
        }
        rows.sort_by(|a, b| b.created_raw.cmp(&a.created_raw));
    }

    let mut out = Vec::new();
    for r in rows {
        out.push(group_public(&s, &r).await?);
    }
    Ok((StatusCode::OK, Json(Value::Array(out))))
}

struct GroupHistoryRow {
    id: i64,
    payment_type: String,
    total_raw: String,
    details_json: String,
    status: String,
    created_raw: String,
    updated_raw: String,
    group_id: String,
    initiated_by: Option<i64>,
    vtu_reference: Option<String>,
}

impl<'r> sqlx::FromRow<'r, sqlx::sqlite::SqliteRow> for GroupHistoryRow {
    fn from_row(row: &'r sqlx::sqlite::SqliteRow) -> Result<Self, sqlx::Error> {
        use sqlx::Row;
        Ok(Self {
            id: row.try_get("id")?,
            payment_type: row.try_get("payment_type")?,
            total_raw: row.try_get("total_amount")?,
            details_json: row.try_get("service_details")?,
            status: row.try_get("status")?,
            created_raw: row.try_get("created_at")?,
            updated_raw: row.try_get("updated_at")?,
            group_id: row.try_get("group_id")?,
            initiated_by: row.try_get("initiated_by_id")?,
            vtu_reference: row.try_get("vtu_reference")?,
        })
    }
}

async fn group_public(
    s: &AppState,
    r: &GroupHistoryRow,
) -> Result<Value, AppError> {
    let group_name: Option<(String,)> =
        sqlx::query_as("SELECT name FROM group_payment_group WHERE id = ?")
            .bind(&r.group_id)
            .fetch_optional(&s.db)
            .await?;
    let (init_name, init_id) = match r.initiated_by {
        Some(uid) => {
            let p: Option<(String, String)> = sqlx::query_as(
                "SELECT surname, other_names FROM accounts_profile WHERE id = ?",
            )
            .bind(uid)
            .fetch_optional(&s.db)
            .await?;
            (
                p.map(|(sn, on)| format!("{sn}, {on}")),
                Some(uid),
            )
        }
        None => (None, None),
    };
    let contribs = pay_models::contributions_with_users(&s.db, r.id).await?;
    let mut items = Vec::new();
    for (c, _uid, name, email) in contribs {
        let cents = crate::wallet::models::parse_cents(&c.amount).ok();
        items.push(ContributionPublic {
            id: c.id,
            member_name: name,
            member_email: email,
            amount: cents
                .map(crate::wallet::models::cents_to_decimal)
                .unwrap_or_else(|| c.amount.clone()),
            status: c.status,
            created_at: format_naive_lagos(&c.created_at),
        });
    }
    let total_cents = crate::wallet::models::parse_cents(&r.total_raw).ok();
    let public = GroupPaymentPublic {
        id: r.id,
        group: r.group_id.clone(),
        group_name: group_name.map(|(n,)| n).unwrap_or_default(),
        initiated_by: init_id,
        initiated_by_name: init_name,
        payment_type: r.payment_type.clone(),
        total_amount: total_cents
            .map(crate::wallet::models::cents_to_decimal)
            .unwrap_or_else(|| r.total_raw.clone()),
        service_details: serde_json::from_str(&r.details_json).unwrap_or(Value::Null),
        status: r.status.clone(),
        vtu_reference: r.vtu_reference.clone(),
        contributions: items,
        created_at: format_created_at_lagos(&r.created_raw),
        updated_at: format_created_at_lagos(&r.updated_raw),
    };
    Ok(serde_json::to_value(&public).unwrap_or(Value::Null))
}
