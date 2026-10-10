//! Payment rows. Mirrors `payments/models.py`.
//!
//! The 14 VTU purchase tables share one shape (owner, service fields,
//! `request_id`, `pending` status, optional VTpass id, timestamps); group,
//! withdrawal, transfer, customer-lookup and webhook-log tables follow.
//! Table/column names match Django exactly.

use sqlx::FromRow;

use crate::wallet::models::parse_cents;

// ---------- generic found-payment (webhook + status views) ----------

/// A purchase row located by `request_id`, with per-kind amount sources.
/// `amount_cents` is set only for tables that carry an amount column
/// (airtime, electricity); `total_cents` only for group payments —
/// mirroring the webhook's `getattr` fallbacks.
pub struct FoundPayment {
    pub model_name: &'static str,
    pub id: i64,
    pub user_id: Option<i64>,
    pub initiated_by: Option<i64>,
    pub status: String,
    pub vtpass_transaction_id: Option<String>,
    pub amount_cents: Option<i64>,
    pub total_cents: Option<i64>,
}

/// (table, model name, amount column) for the 14 VTU tables.
const PURCHASE_TABLES: &[(&str, &str, Option<&str>)] = &[
    ("payments_airtimetopup", "AirtimeTopUp", Some("amount")),
    ("payments_mtndatatopup", "MTNDataTopUp", None),
    ("payments_airteldatatopup", "AirtelDataTopUp", None),
    ("payments_glodatatopup", "GloDataTopUp", None),
    ("payments_etisalatdatatopup", "EtisalatDataTopUp", None),
    ("payments_dstvpayment", "DSTVPayment", None),
    ("payments_gotvpayment", "GOTVPayment", None),
    ("payments_startimespayment", "StartimesPayment", None),
    ("payments_showmaxpayment", "ShowMaxPayment", None),
    ("payments_electricitypayment", "ElectricityPayment", Some("amount")),
    ("payments_waecregitration", "WAECRegitration", None),
    ("payments_waecresultchecker", "WAECResultChecker", None),
    ("payments_jambregistration", "JAMBRegistration", None),
    ("payments_airtime2cash", "Airtime2Cash", Some("amount")),
];

pub async fn find_by_request_id(
    db: &sqlx::PgPool,
    request_id: &str,
) -> Result<Option<FoundPayment>, sqlx::Error> {
    for (table, model_name, amount_col) in PURCHASE_TABLES {
        let amount_sel = match amount_col {
            Some(col) => format!("CAST({col} AS TEXT)"),
            None => "NULL".to_string(),
        };
        let sql = format!(
            "SELECT id, user_id, status, vtpass_transaction_id, {amount_sel} FROM {table} WHERE request_id = $1"
        );
        let row: Option<(i64, Option<i64>, String, Option<String>, Option<String>)> =
            sqlx::query_as(&sql)
                .bind(request_id)
                .fetch_optional(db)
                .await?;
        if let Some((id, user_id, status, vt_id, amount_raw)) = row {
            // `amount` columns are whole naira (IntegerField); parse_cents
            // already yields integer cents.
            let amount_cents = amount_raw
                .as_deref()
                .and_then(|s| parse_cents(s).ok());
            return Ok(Some(FoundPayment {
                model_name,
                id,
                user_id,
                initiated_by: None,
                status,
                vtpass_transaction_id: vt_id,
                amount_cents,
                total_cents: None,
            }));
        }
    }
    // GroupPayment by vtu_reference or service_details.request_id.
    let row: Option<(i64, Option<i64>, String, Option<String>, String)> = sqlx::query_as(
        "SELECT id, initiated_by_id, status, vtpass_transaction_id, CAST(total_amount AS TEXT)
         FROM payments_grouppayment
         WHERE vtu_reference = $1 OR service_details ->> 'request_id' = $2",
    )
    .bind(request_id)
    .bind(request_id)
    .fetch_optional(db)
    .await?;
    if let Some((id, initiated_by, status, vt_id, total_raw)) = row {
        return Ok(Some(FoundPayment {
            model_name: "GroupPayment",
            id,
            user_id: None,
            initiated_by,
            status,
            vtpass_transaction_id: vt_id,
            amount_cents: None,
            total_cents: parse_cents(&total_raw).ok(),
        }));
    }
    Ok(None)
}

pub async fn update_purchase_status(
    db: &sqlx::PgPool,
    table: &str,
    model_name: &str,
    id: i64,
    status: &str,
    vtpass_transaction_id: Option<&str>,
    now: &str,
) -> Result<(), sqlx::Error> {
    let known = PURCHASE_TABLES.iter().any(|(t, _, _)| *t == table)
        || table == "payments_grouppayment";
    assert!(known, "unknown payment table");
    let _ = model_name;
    sqlx::query(&format!(
        "UPDATE {table} SET status = $1, vtpass_transaction_id = COALESCE($2, vtpass_transaction_id), updated_at = $3 WHERE id = $4"
    ))
    .bind(status)
    .bind(vtpass_transaction_id)
    .bind(crate::time::Ts(&now))
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

// ---------- purchase inserts ----------

pub async fn insert_airtime(
    db: &sqlx::PgPool,
    user_id: i64,
    amount_naira: i64,
    network: &str,
    phone: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_airtimetopup (amount, network, phone_number, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, NULL) RETURNING id",
    )
    .bind(amount_naira)
    .bind(network)
    .bind(phone)
    .bind(request_id)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

/// Shared shape for the four data tables.
pub async fn insert_data(
    db: &sqlx::PgPool,
    table: &str,
    user_id: i64,
    plan: &str,
    billers_code: &str,
    phone: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    assert!(matches!(
        table,
        "payments_mtndatatopup"
            | "payments_airteldatatopup"
            | "payments_glodatatopup"
            | "payments_etisalatdatatopup"
    ));
    let res = sqlx::query_as::<_, (i64,)>(&format!(
        "INSERT INTO {table} (plan, billersCode, phone_number, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, NULL) RETURNING id"
    ))
    .bind(plan)
    .bind(billers_code)
    .bind(phone)
    .bind(request_id)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

/// Cable tables. `plan_col` is dstv_plan/gotv_plan/startimes_plan/showmax_plan;
/// `subscription_type` is Some only for DSTV/GOTV.
pub async fn insert_cable(
    db: &sqlx::PgPool,
    table: &str,
    plan_col: &str,
    user_id: i64,
    billers_code: Option<&str>,
    plan: &str,
    subscription_type: Option<&str>,
    phone: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    assert!(matches!(
        table,
        "payments_dstvpayment"
            | "payments_gotvpayment"
            | "payments_startimespayment"
            | "payments_showmaxpayment"
    ));
    // Column order must match the bind order below.
    // NOTE: (no billersCode + subscription_type) panics — no such table.
    let cols = match (billers_code.is_some(), subscription_type.is_some()) {
        (true, true) => format!("billersCode, {plan_col}, subscription_type, phone_number"),
        (true, false) => format!("billersCode, {plan_col}, phone_number"),
        (false, false) => format!("{plan_col}, phone_number"),
        (false, true) => panic!("cable table without billersCode cannot carry subscription_type"),
    };
    let n_params = if billers_code.is_some() && subscription_type.is_some() {
        4
    } else if billers_code.is_some() {
        3
    } else {
        2
    };
    let placeholders: Vec<String> = (1..=n_params).map(|i| format!("${i}")).collect();
    let placeholders = placeholders.join(", ");
    let base = n_params + 1;
    let sql = format!(
        "INSERT INTO {table} ({cols}, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ({placeholders}, ${}, ${}, ${}, 'pending', ${}, NULL) RETURNING id",
        base,
        base + 1,
        base + 2,
        base + 3,
    );
    let mut q = sqlx::query_as::<_, (i64,)>(&sql);
    if let Some(bc) = billers_code {
        q = q.bind(bc);
    }
    q = q.bind(plan);
    if let Some(st) = subscription_type {
        q = q.bind(st);
    }
    q = q.bind(phone);
    let res = q
        .bind(request_id)
        .bind(crate::time::Ts(&now))
        .bind(user_id)
        .bind(crate::time::Ts(&now))
        .fetch_one(db)
        .await?;
    Ok(res.0)
}

pub async fn insert_electricity(
    db: &sqlx::PgPool,
    user_id: i64,
    biller_code: &str,
    amount_naira: i64,
    biller_name: &str,
    meter_type: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_electricitypayment (billerCode, amount, biller_name, meter_type, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, NULL) RETURNING id",
    )
    .bind(biller_code)
    .bind(amount_naira)
    .bind(biller_name)
    .bind(meter_type)
    .bind(request_id)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn insert_exam(
    db: &sqlx::PgPool,
    table: &str,
    user_id: i64,
    phone: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    assert!(matches!(
        table,
        "payments_waecregitration" | "payments_waecresultchecker"
    ));
    let res = sqlx::query_as::<_, (i64,)>(&format!(
        "INSERT INTO {table} (phone_number, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ($1, $2, $3, $4, 'pending', $5, NULL) RETURNING id"
    ))
    .bind(phone)
    .bind(request_id)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn insert_jamb(
    db: &sqlx::PgPool,
    user_id: i64,
    biller_code: &str,
    exam_type: &str,
    phone: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_jambregistration (billerCode, exam_type, phone_number, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, NULL) RETURNING id",
    )
    .bind(biller_code)
    .bind(exam_type)
    .bind(phone)
    .bind(request_id)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn insert_customer_lookup(
    db: &sqlx::PgPool,
    user_id: i64,
    biller: &str,
    meter_number: &str,
    meter_type: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_electricitypaymentcustomers (biller, meter_number, meter_type, user_id)
         VALUES ($1, $2, $3, $4) RETURNING id",
    )
    .bind(biller)
    .bind(meter_number)
    .bind(meter_type)
    .bind(user_id)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

// ---------- group payments (group_payment app tables are read directly) ----------

#[derive(Debug, Clone, FromRow)]
pub struct GroupMemberRow {
    pub id: i64,
    pub role: String,
    pub joined_at: crate::time::NaiveUtc,
    pub group_id: String,
    pub user_id: i64,
    pub locked_amount: i32,
    pub paid_amount: i32,
    pub payment_status: String,
}

pub async fn group_by_id(
    db: &sqlx::PgPool,
    group_id: &str,
) -> Result<Option<(String, String)>, sqlx::Error> {
    sqlx::query_as::<_, (String, String)>(
        "SELECT name, status FROM group_payment_group WHERE id = CAST($1 AS UUID)",
    )
    .bind(group_id)
    .fetch_optional(db)
    .await
}

pub async fn is_group_admin(
    db: &sqlx::PgPool,
    group_id: &str,
    user_id: i64,
) -> Result<bool, sqlx::Error> {
    let row: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM group_payment_groupmember WHERE group_id = CAST($1 AS UUID) AND user_id = $2 AND role IN ('admin', 'owner')",
    )
    .bind(group_id)
    .bind(user_id)
    .fetch_optional(db)
    .await?;
    Ok(row.is_some())
}

pub async fn group_members(
    db: &sqlx::PgPool,
    group_id: &str,
) -> Result<Vec<GroupMemberRow>, sqlx::Error> {
    sqlx::query_as::<_, GroupMemberRow>(
        "SELECT id, role, joined_at, group_id, user_id, locked_amount, paid_amount, payment_status
         FROM group_payment_groupmember WHERE group_id = CAST($1 AS UUID) ORDER BY id",
    )
    .bind(group_id)
    .fetch_all(db)
    .await
}

pub async fn insert_group_payment(
    db: &sqlx::PgPool,
    group_id: &str,
    initiated_by: i64,
    payment_type: &str,
    total_cents: i64,
    service_details_json: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_grouppayment (payment_type, total_amount, service_details, status, created_at, updated_at, group_id, initiated_by_id, vtu_reference)
         VALUES ($1, $2, $3, 'processing', $4, $5, $6, $7, NULL) RETURNING id",
    )
    .bind(payment_type)
    .bind(crate::wallet::models::cents_to_decimal(total_cents))
    .bind(service_details_json)
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .bind(group_id)
    .bind(initiated_by)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn set_group_payment_status(
    db: &sqlx::PgPool,
    id: i64,
    status: &str,
    vtu_reference: Option<&str>,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE payments_grouppayment SET status = $1, vtu_reference = COALESCE($2, vtu_reference), updated_at = $3 WHERE id = $4",
    )
    .bind(status)
    .bind(vtu_reference)
    .bind(crate::time::Ts(&now))
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

pub async fn set_group_status(
    db: &sqlx::PgPool,
    group_id: &str,
    status: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE group_payment_group SET status = $1 WHERE id = CAST($2 AS UUID)")
        .bind(status)
        .bind(group_id)
        .execute(db)
        .await?;
    Ok(())
}

#[derive(Debug, Clone, FromRow)]
pub struct ContributionRow {
    pub id: i64,
    pub amount: String,
    pub status: String,
    pub created_at: crate::time::NaiveUtc,
    pub group_payment_id: i64,
    pub member_id: i64,
}

pub async fn insert_contribution_str(
    db: &sqlx::PgPool,
    group_payment_id: i64,
    member_id: i64,
    amount_display: &str,
    status: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_grouppaymentcontribution (amount, status, created_at, group_payment_id, member_id)
         VALUES (CAST($1 AS NUMERIC), $2, $3, $4, $5) RETURNING id",
    )
    .bind(amount_display)
    .bind(status)
    .bind(crate::time::Ts(&now))
    .bind(group_payment_id)
    .bind(member_id)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn set_contributions_status(
    db: &sqlx::PgPool,
    group_payment_id: i64,
    member_id: Option<i64>,
    status: &str,
) -> Result<(), sqlx::Error> {
    if let Some(mid) = member_id {
        sqlx::query(
            "UPDATE payments_grouppaymentcontribution SET status = $1 WHERE group_payment_id = $2 AND member_id = $3",
        )
        .bind(status)
        .bind(group_payment_id)
        .bind(mid)
        .execute(db)
        .await?;
    } else {
        sqlx::query(
            "UPDATE payments_grouppaymentcontribution SET status = $1 WHERE group_payment_id = $2",
        )
        .bind(status)
        .bind(group_payment_id)
        .execute(db)
        .await?;
    }
    Ok(())
}

pub async fn contributions_with_users(
    db: &sqlx::PgPool,
    group_payment_id: i64,
) -> Result<Vec<(ContributionRow, i64, String, String)>, sqlx::Error> {
    // (contribution, member_user_id, "surname, other_names", email)
    let rows: Vec<(
        i64, String, String, String, i64, i64, i64, String, String, String,
    )> = sqlx::query_as(
        "SELECT c.id, CAST(c.amount AS TEXT), c.status, CAST(c.created_at AS TEXT), c.group_payment_id, c.member_id,
                m.user_id, p.surname, p.other_names, p.email
         FROM payments_grouppaymentcontribution c
         JOIN group_payment_groupmember m ON m.id = c.member_id
         JOIN accounts_profile p ON p.id = m.user_id
         WHERE c.group_payment_id = $1 ORDER BY c.id",
    )
    .bind(group_payment_id)
    .fetch_all(db)
    .await?;
    let mut out = Vec::new();
    for (id, amount, status, created_raw, gpid, mid, uid, surname, other, email) in rows {
        let created = crate::time::parse_stored_dt(&created_raw)
            .unwrap_or(chrono::NaiveDateTime::MIN);
        out.push((
            ContributionRow {
                id,
                amount,
                status,
                created_at: crate::time::NaiveUtc(created),
                group_payment_id: gpid,
                member_id: mid,
            },
            uid,
            format!("{surname}, {other}"),
            email,
        ));
    }
    Ok(out)
}

// ---------- withdrawal / internal transfer ----------

#[derive(Debug, Clone, FromRow)]
pub struct WithdrawalRow {
    pub id: i64,
    pub account_name: String,
    pub account_number: String,
    pub bank_code: String,
    pub bank_name: String,
    pub amount: String,
    pub status: String,
    pub provider: String,
    pub payment_reference: Option<String>,
    pub created_at: crate::time::NaiveUtc,
    pub completed_at: Option<crate::time::NaiveUtc>,
    pub user_id: i64,
    pub recipient_code: Option<String>,
    pub transfer_code: Option<String>,
}

pub async fn insert_withdrawal(
    db: &sqlx::PgPool,
    user_id: i64,
    account_name: &str,
    account_number: &str,
    bank_code: &str,
    bank_name: &str,
    amount_cents: i64,
    payment_reference: &str,
    provider: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_withdrawal (account_name, account_number, bank_code, bank_name, amount, status, payment_reference, created_at, completed_at, user_id, recipient_code, transfer_code, provider)
         VALUES ($1, $2, $3, $4, CAST($5 AS NUMERIC), 'pending', $6, $7, NULL, $8, NULL, NULL, $9) RETURNING id",
    )
    .bind(account_name)
    .bind(account_number)
    .bind(bank_code)
    .bind(bank_name)
    .bind(crate::wallet::models::cents_to_decimal(amount_cents))
    .bind(payment_reference)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(provider)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn find_withdrawal_by_reference_provider(
    db: &sqlx::PgPool,
    payment_reference: &str,
    provider: &str,
) -> Result<Option<WithdrawalRow>, sqlx::Error> {
    sqlx::query_as::<_, WithdrawalRow>(
        "SELECT id, account_name, account_number, bank_code, bank_name, CAST(amount AS TEXT) AS amount, status,
                payment_reference, created_at, completed_at, user_id, recipient_code, transfer_code, provider
         FROM payments_withdrawal WHERE payment_reference = $1 AND provider = $2",
    )
    .bind(payment_reference)
    .bind(provider)
    .fetch_optional(db)
    .await
}

pub async fn get_withdrawal(
    db: &sqlx::PgPool,
    id: i64,
) -> Result<Option<WithdrawalRow>, sqlx::Error> {
    sqlx::query_as::<_, WithdrawalRow>(
        "SELECT id, account_name, account_number, bank_code, bank_name, CAST(amount AS TEXT) AS amount, status,
                payment_reference, created_at, completed_at, user_id, recipient_code, transfer_code, provider
         FROM payments_withdrawal WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(db)
    .await
}

pub async fn set_withdrawal_status(
    db: &sqlx::PgPool,
    id: i64,
    status: &str,
    recipient_code: Option<&str>,
    transfer_code: Option<&str>,
    completed_at: Option<&str>,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE payments_withdrawal SET status = $1, recipient_code = COALESCE($2, recipient_code),
         transfer_code = COALESCE($3, transfer_code), completed_at = COALESCE($4, completed_at) WHERE id = $5",
    )
    .bind(status)
    .bind(recipient_code)
    .bind(transfer_code)
    .bind(completed_at.map(crate::time::Ts))
    .bind(id)
    .execute(db)
    .await?;
    Ok(())
}

#[derive(Debug, Clone, FromRow)]
pub struct InternalTransferRow {
    pub id: i64,
    pub reference_id: Option<String>,
    pub amount: String,
    pub recepiant_dva_account_number: String,
    pub recepiant_email: String,
    pub recepiant_full_name: String,
    pub transfer_method: String,
    pub created_at: crate::time::NaiveUtc,
    pub completed_at: Option<crate::time::NaiveUtc>,
    pub status: String,
}

pub async fn insert_internal_transfer(
    db: &sqlx::PgPool,
    reference_id: &str,
    user_id: i64,
    amount_cents: i64,
    dva_number: &str,
    email: &str,
    full_name: &str,
    transfer_method: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_internaltransfer (reference_id, amount, recepiant_dva_account_number, recepiant_email, recepiant_full_name, transfer_method, created_at, completed_at, status, user_id)
         VALUES ($1, CAST($2 AS NUMERIC), $3, $4, $5, $6, $7, NULL, 'pending', $8) RETURNING id",
    )
    .bind(reference_id)
    .bind(crate::wallet::models::cents_to_decimal(amount_cents))
    .bind(dva_number)
    .bind(email)
    .bind(full_name)
    .bind(transfer_method)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .fetch_one(db)
    .await?;
    Ok(res.0)
}

pub async fn set_internal_transfer_status(
    db: &sqlx::PgPool,
    id: i64,
    status: &str,
    completed_at: Option<&str>,
) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE payments_internaltransfer SET status = $1, completed_at = COALESCE($2, completed_at) WHERE id = $3")
        .bind(status)
        .bind(completed_at.map(crate::time::Ts))
        .bind(id)
        .execute(db)
        .await?;
    Ok(())
}

pub async fn find_internal_transfer(
    db: &sqlx::PgPool,
    reference_id: &str,
) -> Result<Option<(InternalTransferRow, i64)>, sqlx::Error> {
    let row: Option<(
        i64, Option<String>, String, String, String, String, String,
        chrono::DateTime<chrono::Utc>, Option<chrono::DateTime<chrono::Utc>>, String, i64,
    )> = sqlx::query_as(
        "SELECT id, reference_id, CAST(amount AS TEXT), recepiant_dva_account_number, recepiant_email,
                recepiant_full_name, transfer_method, created_at, completed_at, status, user_id
         FROM payments_internaltransfer WHERE reference_id = $1",
    )
    .bind(reference_id)
    .fetch_optional(db)
    .await?;
    Ok(row.map(
        |(
            id, reference_id, amount, dva, email, full_name, method,
            created_at, completed_at, status, user_id,
        )| {
            (
                InternalTransferRow {
                    id,
                    reference_id,
                    amount,
                    recepiant_dva_account_number: dva,
                    recepiant_email: email,
                    recepiant_full_name: full_name,
                    transfer_method: method,
                    created_at: crate::time::NaiveUtc(created_at.naive_utc()),
                    completed_at: completed_at.map(|d| crate::time::NaiveUtc(d.naive_utc())),
                    status,
                },
                user_id,
            )
        },
    ))
}

// ---------- webhook log ----------

pub async fn log_webhook(
    db: &sqlx::PgPool,
    request_id: &str,
    transaction_id: &str,
    vt_status: &str,
    code: &str,
    amount_display: Option<&str>,
    raw_payload: &str,
    is_processed: bool,
    error: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO payments_vtpasswebhooklog (request_id, transaction_id, vt_status, code, amount, raw_payload, is_processed, error, created_at, updated_at)
         VALUES ($1, $2, $3, $4, CAST($5 AS NUMERIC), $6, $7, $8, $9, $10)
         ON CONFLICT(request_id, transaction_id, vt_status) DO NOTHING",
    )
    .bind(request_id)
    .bind(transaction_id)
    .bind(vt_status)
    .bind(code)
    .bind(amount_display)
    .bind(raw_payload)
    .bind(is_processed)
    .bind(error)
    .bind(crate::time::Ts(&now))
    .bind(crate::time::Ts(&now))
    .execute(db)
    .await?;
    Ok(())
}

pub async fn webhook_log_processed(
    db: &sqlx::PgPool,
    request_id: &str,
    transaction_id: &str,
    vt_status: &str,
) -> Result<Option<bool>, sqlx::Error> {
    let row: Option<(bool,)> = sqlx::query_as(
        "SELECT is_processed FROM payments_vtpasswebhooklog WHERE request_id = $1 AND transaction_id = $2 AND vt_status = $3",
    )
    .bind(request_id)
    .bind(transaction_id)
    .bind(vt_status)
    .fetch_optional(db)
    .await?;
    Ok(row.map(|(v,)| v))
}

pub async fn mark_webhook_processed(
    db: &sqlx::PgPool,
    request_id: &str,
    transaction_id: &str,
    vt_status: &str,
    code: &str,
    amount_display: Option<&str>,
    raw_payload: &str,
    error: &str,
    now: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE payments_vtpasswebhooklog SET code = $1, amount = COALESCE(CAST($2 AS NUMERIC), amount), raw_payload = $3,
         is_processed = TRUE, error = $4, updated_at = $5 WHERE request_id = $6 AND transaction_id = $7 AND vt_status = $8",
    )
    .bind(code)
    .bind(amount_display)
    .bind(raw_payload)
    .bind(error)
    .bind(crate::time::Ts(&now))
    .bind(request_id)
    .bind(transaction_id)
    .bind(vt_status)
    .execute(db)
    .await?;
    Ok(())
}

/// Betting-account funding row (`payments_bettingpayment`, Django migration
/// `0016_bettingpayment`). DDL lives in Django; tests carry their own DDL.
pub async fn insert_betting(
    db: &sqlx::PgPool,
    user_id: i64,
    provider: &str,
    customer_id: &str,
    amount_naira: i64,
    phone: &str,
    request_id: &str,
    now: &str,
) -> Result<i64, sqlx::Error> {
    let res = sqlx::query_as::<_, (i64,)>(
        "INSERT INTO payments_bettingpayment (provider, customer_id, amount, phone_number, request_id, created_at, user_id, status, updated_at, vtpass_transaction_id)
         VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, NULL) RETURNING id",
    )
    .bind(provider)
    .bind(customer_id)
    .bind(amount_naira)
    .bind(phone)
    .bind(request_id)
    .bind(crate::time::Ts(&now))
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .fetch_one(db)
    .await?;
    Ok(res.0)
}
