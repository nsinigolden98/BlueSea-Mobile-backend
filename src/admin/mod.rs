//! Staff admin backend. Mirrors the Django admin surface as JSON + serves
//! the React panel: per-app submodules (`accounts`, `payments`, …) each
//! register their models, and `router()` exposes them under `/admin/api/`.
//!
//! Every model is full CRUD through one generic executor driven by a
//! [`ModelDef`]: reads select every column as text (no decode issues),
//! writes bind text with `CAST($N AS <type>)`. The frontend fetches the
//! registry at `GET /admin/api/models` and renders all pages generically.

pub mod accounts;
pub mod affiliate;
pub mod autotopup;
pub mod bonus;
pub mod broadcast;
pub mod group_payment;
pub mod loyalty_market;
pub mod market_place;
pub mod notifications;
pub mod payments;
pub mod support;
pub mod transactions;
pub mod user_preference;
pub mod wallet;

use std::collections::HashMap;

use axum::{
    Json,
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
};
use serde_json::{Value, json};

use crate::accounts::models::Profile;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;

pub type Resp = (StatusCode, Json<Value>);

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ColType {
    Int,
    Bool,
    Numeric,
    DateTime,
    Date,
    Uuid,
    Json,
    Text,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum PkType {
    Int,
    Uuid,
}

/// One admin-managed model.
#[derive(Debug, Clone)]
pub struct ModelDef {
    /// URL slug, e.g. `accounts.Profile`.
    pub name: &'static str,
    /// Human label, e.g. `Users`.
    pub label: &'static str,
    pub table: &'static str,
    pub pk: &'static str,
    pub pk_type: PkType,
    /// `(column, type)` in table order.
    pub columns: &'static [(&'static str, ColType)],
    /// Text columns searched by `?search=`.
    pub search: &'static [&'static str],
    /// Default `ORDER BY`, e.g. `"-created_at"`.
    pub default_order: &'static str,
}

impl ModelDef {
    fn col_type(&self, col: &str) -> ColType {
        self.columns.iter().find(|(c, _)| *c == col).map(|(_, t)| *t).unwrap_or(ColType::Text)
    }

    fn cast(&self, col: &str, param: &str) -> String {
        let sql_type = match self.col_type(col) {
            ColType::Int => "BIGINT",
            ColType::Bool => "BOOLEAN",
            ColType::Numeric => "NUMERIC",
            ColType::DateTime => "TIMESTAMPTZ",
            ColType::Date => "DATE",
            ColType::Uuid => "UUID",
            ColType::Json => "JSONB",
            ColType::Text => "TEXT",
        };
        format!("CAST({param} AS {sql_type})")
    }

    fn select_list(&self) -> String {
        self.columns
            .iter()
            .map(|(c, _)| format!("CAST({c} AS TEXT) AS {c}"))
            .collect::<Vec<_>>()
            .join(", ")
    }

    fn order_clause(&self, ordering: Option<&str>) -> String {
        let mut key = ordering.unwrap_or(self.default_order);
        let desc = key.starts_with('-');
        if desc {
            key = &key[1..];
        }
        if !self.columns.iter().any(|(c, _)| *c == key) {
            key = self.default_order.trim_start_matches('-');
        }
        // Order by the real column (not the text cast) for sane sorting.
        if desc {
            format!("{key} DESC")
        } else {
            format!("{key} ASC")
        }
    }
}

pub fn err_json(e: AppError) -> Resp {
    (e.status, Json(json!({"detail": e.message})))
}

/// Hash a raw `password` on profile create/update (Django `set_password`
/// equivalent — never store it raw like a plain column write would).
fn hash_profile_password(def: &ModelDef, body: &mut Value) {
    if def.table != "accounts_profile" {
        return;
    }
    let Some(obj) = body.as_object_mut() else {
        return;
    };
    if let Some(Value::String(pw)) = obj.get("password") {
        // Skip values that already look hashed (PBKDF2/Django format).
        if !(pw.starts_with("pbkdf2_") || pw.starts_with("argon2")) {
            obj.insert(
                "password".to_string(),
                Value::String(crate::auth::password::hash_password(pw)),
            );
        }
    }
}

pub fn forbidden() -> Resp {
    (
        StatusCode::FORBIDDEN,
        Json(json!({"detail": "Admin access required."})),
    )
}

pub async fn require_staff(s: &AppState, headers: HeaderMap) -> Result<Profile, Resp> {
    let user = auth_user(State(s.clone()), headers).await.map_err(|e| {
        (StatusCode::UNAUTHORIZED, Json(json!({"detail": e.message})))
    })?;
    if !(user.is_staff || user.is_superuser) {
        return Err(forbidden());
    }
    Ok(user)
}

fn parse_id(def: &ModelDef, raw: &str) -> Result<String, Resp> {
    match def.pk_type {
        PkType::Int => raw
            .trim()
            .parse::<i64>()
            .map(|v| v.to_string())
            .map_err(|_| {
                (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})))
            }),
        PkType::Uuid => uuid::Uuid::parse_str(raw.trim())
            .map(|u| u.hyphenated().to_string())
            .map_err(|_| {
                (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})))
            }),
    }
}

/// JSON value to text bind (numbers/bools stringified; null handled by caller).
fn val_text(v: &Value) -> Option<String> {
    match v {
        Value::Null => None,
        Value::String(s) => Some(s.clone()),
        Value::Bool(b) => Some(b.to_string()),
        Value::Number(n) => Some(n.to_string()),
        Value::Array(_) | Value::Object(_) => Some(v.to_string()),
    }
}

pub async fn list_rows(
    s: &AppState,
    def: &ModelDef,
    params: &HashMap<String, String>,
) -> Result<Value, AppError> {
    let page = params.get("page").and_then(|v| v.parse::<i64>().ok()).filter(|p| *p >= 1).unwrap_or(1);
    let size = params
        .get("page_size")
        .and_then(|v| v.parse::<i64>().ok())
        .filter(|n| *n >= 1)
        .map(|n| n.min(100))
        .unwrap_or(25);
    let mut where_sql = "TRUE".to_string();
    let mut binds: Vec<String> = Vec::new();
    if let Some(q) = params.get("search").filter(|v| !v.is_empty()) {
        let like = format!("%{}%", q.replace('\\', "\\\\").replace('%', "\\%").replace('_', "\\_"));
        let ors: Vec<String> = def
            .search
            .iter()
            .enumerate()
            .map(|(i, c)| format!("{c} LIKE ${} ESCAPE '\\'", binds.len() + i + 1))
            .collect();
        if !ors.is_empty() {
            where_sql = format!("({})", ors.join(" OR "));
            for _ in def.search {
                binds.push(like.clone());
            }
        }
    }
    let order = def.order_clause(params.get("ordering").map(|v| v.as_str()));
    let count: (i64,) = {
        let sql = format!("SELECT COUNT(*) FROM {} WHERE {where_sql}", def.table);
        let mut q = sqlx::query_as(&sql);
        for b in &binds {
            q = q.bind(b);
        }
        q.fetch_one(&s.db).await?
    };
    let offset = (page - 1) * size;
    let sql = format!(
        "SELECT {} FROM {} WHERE {where_sql} ORDER BY {order} LIMIT ${} OFFSET ${}",
        def.select_list(),
        def.table,
        binds.len() + 1,
        binds.len() + 2,
    );
    let mut q = sqlx::query(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    let rows = q
        .bind(size)
        .bind(offset)
        .fetch_all(&s.db)
        .await?;
    let mut out = Vec::new();
    for row in rows {
        use sqlx::Row;
        let mut obj = serde_json::Map::new();
        for (col, _) in def.columns {
            let v: Option<String> = row.try_get(*col).unwrap_or(None);
            obj.insert(col.to_string(), v.map(Value::String).unwrap_or(Value::Null));
        }
        out.push(Value::Object(obj));
    }
    Ok(json!({"count": count.0, "results": out}))
}

pub async fn get_row(s: &AppState, def: &ModelDef, id: &str) -> Result<Option<Value>, AppError> {
    let sql = format!(
        "SELECT {} FROM {} WHERE {} = {}",
        def.select_list(),
        def.table,
        def.pk,
        def.cast(def.pk, "$1"),
    );
    let row: Option<sqlx::postgres::PgRow> = sqlx::query(&sql)
        .bind(id)
        .fetch_optional(&s.db)
        .await?;
    Ok(row.map(|row| {
        use sqlx::Row;
        let mut obj = serde_json::Map::new();
        for (col, _) in def.columns {
            let v: Option<String> = row.try_get(*col).unwrap_or(None);
            obj.insert(col.to_string(), v.map(Value::String).unwrap_or(Value::Null));
        }
        Value::Object(obj)
    }))
}

pub async fn create_row(s: &AppState, def: &ModelDef, body: &Value) -> Result<Value, AppError> {
    let mut body = body.clone();
    hash_profile_password(def, &mut body);
    // Django auto_now_add/auto_now: fill timestamps when absent.
    if let Some(obj) = body.as_object_mut() {
        let now = crate::time::now_str();
        for stamp in ["created_at", "updated_at"] {
            if def.columns.iter().any(|(c, _)| *c == stamp) && !obj.contains_key(stamp) {
                obj.insert(stamp.to_string(), Value::String(now.clone()));
            }
        }
    }
    let obj = body.as_object().ok_or_else(|| AppError::bad_request("Invalid object"))?;
    let mut cols: Vec<String> = Vec::new();
    let mut vals: Vec<String> = Vec::new();
    let mut binds: Vec<String> = Vec::new();
    // Serial PKs are database-generated; UUID PKs are minted here (Django default=uuid4).
    let gen_uuid = def.pk_type == PkType::Uuid;
    if gen_uuid {
        cols.push(def.pk.to_string());
        vals.push(format!("CAST(${} AS UUID)", binds.len() + 1));
        binds.push(uuid::Uuid::new_v4().hyphenated().to_string());
    }
    for (col, _) in def.columns {
        if *col == def.pk {
            continue;
        }
        let Some(text) = obj.get(*col).and_then(val_text) else {
            continue;
        };
        cols.push(col.to_string());
        vals.push(def.cast(col, &format!("${}", binds.len() + 1)));
        binds.push(text);
    }
    if cols.is_empty() {
        return Err(AppError::bad_request("No fields provided"));
    }
    let sql = format!(
        "INSERT INTO {} ({}) VALUES ({}) RETURNING {}",
        def.table,
        cols.join(", "),
        vals.join(", "),
        def.pk,
    );
    let mut q = sqlx::query(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    let row = q.fetch_one(&s.db).await.map_err(|e| {
        tracing::error!("admin create failed: {e}");
        AppError::bad_request(format!("Create failed: {e}"))
    })?;
    use sqlx::Row;
    let id: String = match def.pk_type {
        PkType::Int => row.try_get::<i64, _>(def.pk).map(|v| v.to_string()).unwrap_or_default(),
        PkType::Uuid => row.try_get::<uuid::Uuid, _>(def.pk).map(|u| u.hyphenated().to_string()).unwrap_or_default(),
    };
    Ok(json!({"id": id}))
}

pub async fn update_row(
    s: &AppState,
    def: &ModelDef,
    id: &str,
    body: &Value,
    partial: bool,
) -> Result<Option<Value>, AppError> {
    let mut body = body.clone();
    hash_profile_password(def, &mut body);
    if let Some(obj) = body.as_object_mut() {
        if def.columns.iter().any(|(c, _)| *c == "updated_at") && !obj.contains_key("updated_at") {
            obj.insert("updated_at".to_string(), Value::String(crate::time::now_str()));
        }
    }
    let obj = body.as_object().ok_or_else(|| AppError::bad_request("Invalid object"))?;
    let mut sets: Vec<String> = Vec::new();
    let mut binds: Vec<String> = Vec::new();
    for (col, _) in def.columns {
        if *col == def.pk {
            continue;
        }
        match obj.get(*col) {
            None if partial => continue,
            None => continue,
            Some(v) => {
                if v.is_null() {
                    sets.push(format!("{col} = NULL"));
                } else if let Some(text) = val_text(v) {
                    sets.push(format!("{col} = {}", def.cast(col, &format!("${}", binds.len() + 1))));
                    binds.push(text);
                }
            }
        }
    }
    if sets.is_empty() {
        return Err(AppError::bad_request("No editable fields provided"));
    }
    let sql = format!(
        "UPDATE {} SET {} WHERE {} = {}",
        def.table,
        sets.join(", "),
        def.pk,
        def.cast(def.pk, &format!("${}", binds.len() + 1)),
    );
    let mut q = sqlx::query(&sql);
    for b in &binds {
        q = q.bind(b);
    }
    let res = q.bind(id).execute(&s.db).await.map_err(|e| {
        tracing::error!("admin update failed: {e}");
        AppError::bad_request(format!("Update failed: {e}"))
    })?;
    if res.rows_affected() == 0 {
        return Ok(None);
    }
    Ok(get_row(s, def, id).await?)
}

pub async fn delete_row(s: &AppState, def: &ModelDef, id: &str) -> Result<bool, AppError> {
    let sql = format!(
        "DELETE FROM {} WHERE {} = {}",
        def.table,
        def.pk,
        def.cast(def.pk, "$1"),
    );
    let res = sqlx::query(&sql).bind(id).execute(&s.db).await?;
    Ok(res.rows_affected() > 0)
}

/// Look up a registered model by slug (`app.Model`).
pub fn find_model(slug: &str) -> Option<ModelDef> {
    all_models().into_iter().find(|m| m.name == slug)
}

/// Dashboard counts for every registered model.
pub async fn dashboard(s: &AppState) -> Value {
    let mut out = Vec::new();
    for m in all_models() {
        let count: i64 = sqlx::query_as(&format!("SELECT COUNT(*) FROM {}", m.table))
            .fetch_one(&s.db)
            .await
            .map(|r: (i64,)| r.0)
            .unwrap_or(0);
        out.push(json!({"model": m.name, "label": m.label, "count": count}));
    }
    Value::Array(out)
}

/// Cashflow summary for the admin dashboard: total wallet inflow (CREDIT)
/// vs outflow (DEBIT) over the last N days, plus a per-day series for the
/// chart. Only `COMPLETED` ledger rows count as real money movement.
pub async fn cashflow(s: &AppState, days: i64) -> Value {
    let days = days.clamp(7, 90);
    let rows: Vec<(String, String, String)> = sqlx::query_as(
        "SELECT TO_CHAR(d.day, 'YYYY-MM-DD'),
                COALESCE(CAST(SUM(CASE WHEN t.transaction_type = 'CREDIT' AND t.status = 'COMPLETED' THEN t.amount ELSE 0 END) AS TEXT), '0'),
                COALESCE(CAST(SUM(CASE WHEN t.transaction_type = 'DEBIT' AND t.status = 'COMPLETED' THEN t.amount ELSE 0 END) AS TEXT), '0')
         FROM (SELECT (CURRENT_DATE - (g || ' day')::interval)::date AS day
               FROM generate_series(0, $1 - 1) g) d
         LEFT JOIN transactions_wallettransaction t
           ON t.created_at::date = d.day
         GROUP BY d.day ORDER BY d.day",
    )
    .bind(days)
    .fetch_all(&s.db)
    .await
    .unwrap_or_default();
    let mut inflow_total = 0f64;
    let mut outflow_total = 0f64;
    let series: Vec<Value> = rows
        .iter()
        .map(|(date, inflow, outflow)| {
            let i: f64 = inflow.parse().unwrap_or(0.0);
            let o: f64 = outflow.parse().unwrap_or(0.0);
            inflow_total += i;
            outflow_total += o;
            json!({"date": date, "inflow": i, "outflow": o})
        })
        .collect();
    json!({
        "days": days,
        "totals": {
            "inflow": inflow_total,
            "outflow": outflow_total,
            "net": inflow_total - outflow_total,
        },
        "series": series,
    })
}

fn crud_routes(router: axum::Router<AppState>, prefix: &str, slug: &str) -> axum::Router<AppState> {
    use axum::routing::{delete, get, post};
    let slug = slug.to_string();
    let list_slug = slug.clone();
    let get_slug = slug.clone();
    let post_slug = slug.clone();
    let put_slug = slug.clone();
    let del_slug = slug.clone();
    router
        .route(
            &format!("{prefix}/{slug}/"),
            get(
                move |State(s): State<AppState>, headers: HeaderMap, Query(params): Query<HashMap<String, String>>| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let Some(def) = find_model(&list_slug) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    match list_rows(&s, &def, &params).await {
                        Ok(v) => (StatusCode::OK, Json(v)),
                        Err(e) => err_json(e),
                    }
                },
            )
            .post(
                move |State(s): State<AppState>, headers: HeaderMap, Json(body): Json<Value>| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let Some(def) = find_model(&post_slug) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    match create_row(&s, &def, &body).await {
                        Ok(v) => (StatusCode::CREATED, Json(v)),
                        Err(e) => err_json(e),
                    }
                },
            ),
        )
        .route(
            &format!("{prefix}/{slug}/{{id}}/"),
            get(
                move |State(s): State<AppState>, headers: HeaderMap, Path(id): Path<String>| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let Some(def) = find_model(&get_slug) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    let Ok(pid) = parse_id(&def, &id) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    match get_row(&s, &def, &pid).await {
                        Ok(Some(v)) => (StatusCode::OK, Json(v)),
                        Ok(None) => (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."}))),
                        Err(e) => err_json(e),
                    }
                },
            )
            .put(
                move |State(s): State<AppState>, headers: HeaderMap, Path(id): Path<String>, Json(body): Json<Value>| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let Some(def) = find_model(&put_slug) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    let Ok(pid) = parse_id(&def, &id) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    match update_row(&s, &def, &pid, &body, true).await {
                        Ok(Some(v)) => (StatusCode::OK, Json(v)),
                        Ok(None) => (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."}))),
                        Err(e) => err_json(e),
                    }
                },
            )
            .delete(
                move |State(s): State<AppState>, headers: HeaderMap, Path(id): Path<String>| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let Some(def) = find_model(&del_slug) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    let Ok(pid) = parse_id(&def, &id) else {
                        return (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."})));
                    };
                    match delete_row(&s, &def, &pid).await {
                        Ok(true) => (StatusCode::NO_CONTENT, Json(Value::Null)),
                        Ok(false) => (StatusCode::NOT_FOUND, Json(json!({"detail": "Not found."}))),
                        Err(e) => err_json(e),
                    }
                },
            ),
        )
}

/// SPA fallback: `/admin` (except `/admin/api/*`) serves the React panel's
/// `index.html`; anything else is a plain 404 so mistyped API paths never
/// return HTML. Missing `dist/` (panel not built yet) is a 404 with a hint.
pub async fn spa_fallback(uri: axum::http::Uri) -> impl axum::response::IntoResponse {
    use axum::response::IntoResponse;
    let path = uri.path();
    if path == "/admin" || path == "/admin/" {
        return serve_index().await;
    }
    if let Some(rest) = path.strip_prefix("/admin/") {
        if rest.starts_with("api/") {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({"detail": "Not found."})),
            )
                .into_response();
        }
        // Static asset? Serve from dist, else the SPA shell.
        let dist = std::path::Path::new("admin-panel/dist");
        let candidate = dist.join(rest.trim_start_matches('/'));
        if candidate.is_file() {
            let content_type = match candidate.extension().and_then(|e| e.to_str()) {
                Some("js") => "application/javascript",
                Some("css") => "text/css",
                Some("html") => "text/html",
                Some("json") => "application/json",
                Some("png") => "image/png",
                Some("svg") => "image/svg+xml",
                Some("ico") => "image/x-icon",
                _ => "application/octet-stream",
            };
            if let Ok(bytes) = tokio::fs::read(&candidate).await {
                return (
                    StatusCode::OK,
                    [(axum::http::header::CONTENT_TYPE, content_type)],
                    bytes,
                )
                    .into_response();
            }
        }
        return serve_index().await;
    }
    (
        StatusCode::NOT_FOUND,
        Json(json!({"detail": "Not found."})),
    )
        .into_response()
}

async fn serve_index() -> axum::response::Response {
    use axum::response::IntoResponse;
    match tokio::fs::read("admin-panel/dist/index.html").await {
        Ok(bytes) => (
            StatusCode::OK,
            [(axum::http::header::CONTENT_TYPE, "text/html")],
            bytes,
        )
            .into_response(),
        Err(_) => (
            StatusCode::NOT_FOUND,
            Json(json!({"detail": "Admin panel not built. Run `npm run build` in admin-panel/."})),
        )
            .into_response(),
    }
}

/// Full admin router: registry + dashboard + every registered model.
pub fn router(state: AppState) -> axum::Router {
    use axum::routing::get;
    let mut router = axum::Router::new()
        .route(
            "/admin/api/models/",
            get(
                |State(s): State<AppState>, headers: HeaderMap| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let models: Vec<Value> = all_models()
                        .into_iter()
                        .map(|m| {
                            json!({
                                "name": m.name,
                                "label": m.label,
                                "table": m.table,
                                "pk": m.pk,
                                "pk_type": match m.pk_type {
                                    PkType::Int => "int",
                                    PkType::Uuid => "uuid",
                                },
                                "columns": m.columns.iter().map(|(c, t)| json!({
                                    "name": c,
                                    "type": match t {
                                        ColType::Int => "int",
                                        ColType::Bool => "bool",
                                        ColType::Numeric => "numeric",
                                        ColType::DateTime => "datetime",
                                        ColType::Date => "date",
                                        ColType::Uuid => "uuid",
                                        ColType::Json => "json",
                                        ColType::Text => "text",
                                    },
                                })).collect::<Vec<_>>(),
                                "search": m.search,
                                "default_order": m.default_order,
                            })
                        })
                        .collect();
                    (StatusCode::OK, Json(json!(models)))
                },
            ),
        )
        .route(
            "/admin/api/dashboard/",
            get(|State(s): State<AppState>, headers: HeaderMap| async move {
                let _admin = match require_staff(&s, headers).await {
                    Ok(u) => u,
                    Err(e) => return e,
                };
                (StatusCode::OK, Json(dashboard(&s).await))
            }),
        )
        .route(
            "/admin/api/cashflow/",
            get(
                |State(s): State<AppState>,
                 headers: HeaderMap,
                 Query(params): Query<HashMap<String, String>>| async move {
                    let _admin = match require_staff(&s, headers).await {
                        Ok(u) => u,
                        Err(e) => return e,
                    };
                    let days = params
                        .get("days")
                        .and_then(|v| v.parse::<i64>().ok())
                        .unwrap_or(30);
                    (StatusCode::OK, Json(cashflow(&s, days).await))
                },
            ),
        );
    for m in all_models() {
        router = crud_routes(router, "/admin/api", m.name);
    }
    router = router
        .route(
            "/admin/api/accounts.Profile/{id}/unfreeze/",
            axum::routing::post(accounts::unfreeze_profile),
        )
        .route(
            "/admin/api/market_place.TicketVendor/{id}/approve/",
            axum::routing::post(market_place::approve_vendor),
        )
        .route(
            "/admin/api/market_place.TicketVendor/{id}/reject/",
            axum::routing::post(market_place::reject_vendor),
        );
    router.with_state(state)
}

fn all_models() -> Vec<ModelDef> {
    let mut out = Vec::new();
    accounts::register(&mut out);
    affiliate::register(&mut out);
    autotopup::register(&mut out);
    bonus::register(&mut out);
    broadcast::register(&mut out);
    group_payment::register(&mut out);
    loyalty_market::register(&mut out);
    market_place::register(&mut out);
    notifications::register(&mut out);
    payments::register(&mut out);
    support::register(&mut out);
    transactions::register(&mut out);
    user_preference::register(&mut out);
    wallet::register(&mut out);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;

    async fn memory_db() -> sqlx::PgPool {
        let pool = crate::db::test_support::fresh_db(&[
            "CREATE TABLE accounts_profile (id BIGSERIAL PRIMARY KEY, password varchar(128) NOT NULL,
             last_login TIMESTAMPTZ NULL, is_superuser BOOLEAN NOT NULL, first_name varchar(150) NOT NULL, last_name varchar(150) NOT NULL,
             date_joined TIMESTAMPTZ NOT NULL, email varchar(300) NOT NULL UNIQUE, surname varchar(100) NOT NULL, other_names varchar(100) NOT NULL,
             phone varchar(200) NULL, image varchar(100) NULL, verification_code varchar(100) NULL, is_active BOOLEAN NOT NULL,
             is_staff BOOLEAN NOT NULL, is_admin BOOLEAN NOT NULL, role varchar(200) NOT NULL, email_verified BOOLEAN NOT NULL,
             created_on TIMESTAMPTZ NOT NULL, pin_is_set BOOLEAN NOT NULL, transaction_pin varchar(255) NULL,
             referral_code varchar(6) NOT NULL UNIQUE, pin_failed_attempts integer NOT NULL, pin_locked_until TIMESTAMPTZ NULL, nin_encrypted text NULL, bvn_encrypted text NULL, house_address text NULL, utility_bill_image varchar(100) NULL, is_frozen BOOLEAN NOT NULL DEFAULT FALSE, frozen_reason varchar(200) NULL, \"has_DVA\" BOOLEAN NOT NULL)",
            "CREATE TABLE broadcast_broadcast (id BIGSERIAL PRIMARY KEY, kind varchar(20) NOT NULL,
             title varchar(200) NOT NULL, message text NOT NULL, email_subject varchar(200) NOT NULL,
             template varchar(200) NOT NULL, month_key varchar(7) NULL, status varchar(20) NOT NULL,
             total integer NOT NULL, sent_count integer NOT NULL, failed_count integer NOT NULL,
             created_by_id bigint NULL, created_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ NULL)",
            "CREATE TABLE token_blacklist_outstandingtoken (token text NOT NULL, created_at TIMESTAMPTZ NULL,
             expires_at TIMESTAMPTZ NOT NULL, user_id bigint NULL, jti varchar(255) NOT NULL UNIQUE,
             id BIGSERIAL PRIMARY KEY)",
            "CREATE TABLE token_blacklist_blacklistedtoken (blacklisted_at TIMESTAMPTZ NOT NULL,
             token_id bigint NOT NULL UNIQUE, id BIGSERIAL PRIMARY KEY)",
        ])
        .await;
        for (email, staff, code) in [("staff@x.com", true, "STAFF1"), ("user@x.com", false, "USER01")] {
            sqlx::query(
                "INSERT INTO accounts_profile (password, is_superuser, first_name, last_name, date_joined, email, surname, other_names,
                 is_active, is_staff, is_admin, role, email_verified, created_on, pin_is_set, referral_code, pin_failed_attempts, \"has_DVA\")
                 VALUES ('x', FALSE, '', '', '2026-01-01 00:00:00', $1, 'S', 'O', TRUE, $2, FALSE, 'user', TRUE, '2026-01-01 00:00:00', FALSE, $3, 0, FALSE)",
            )
            .bind(email)
            .bind(staff)
            .bind(code)
            .execute(&pool)
            .await
            .unwrap();
        }
        pool
    }

    fn test_state(db: sqlx::PgPool) -> (AppState, String) {
        let mut config = crate::settings::Config::from_env();
        config.email_backend = "console".to_string();
        config.debug = true;
        let secret = config.secret_key.clone();
        (
            AppState {
                db,
                config,
                http: reqwest::Client::new(),
                wallet_hub: crate::wallet::hub::WalletHub::default(),
                support_hub: crate::support::hub::SupportHub::default(),
            plans_store: crate::plans_cache::PlansStore::default(),
            notification_hub: crate::notifications::hub::NotificationHub::default(),
            },
            secret,
        )
    }

    fn bearer(secret: &str, user_id: i64) -> HeaderMap {
        let (access, _) = crate::auth::jwt::create_token_pair(user_id, "user", secret).unwrap();
        let mut h = HeaderMap::new();
        h.insert("authorization", format!("Bearer {access}").parse().unwrap());
        h
    }

    fn broadcast_def() -> ModelDef {
        find_model("broadcast.Broadcast").expect("broadcast model registered")
    }

    #[tokio::test]
    async fn gate_rejects_non_staff() {
        let db = memory_db().await;
        let (s, secret) = test_state(db);
        // No token -> 401.
        assert!(require_staff(&s, HeaderMap::new()).await.is_err());
        // Non-staff user (id 2) -> 403.
        let err = require_staff(&s, bearer(&secret, 2)).await.unwrap_err();
        assert_eq!(err.0, StatusCode::FORBIDDEN);
        // Staff user (id 1) passes.
        let staff = require_staff(&s, bearer(&secret, 1)).await.unwrap();
        assert!(staff.is_staff);
    }

    #[tokio::test]
    async fn crud_roundtrip_and_registry() {
        let db = memory_db().await;
        let (s, _) = test_state(db.clone());
        // Registry covers every ported app.
        let names: Vec<&str> = all_models().iter().map(|m| m.name).collect();
        for want in [
            "accounts.Profile",
            "payments.AirtimeTopUp",
            "market_place.TicketVendor",
            "support.SupportTicket",
            "broadcast.Broadcast",
            "affiliate.AffiliateSale",
        ] {
            assert!(names.contains(&want), "missing {want}");
        }
        // Create -> get -> list -> update -> delete.
        let def = broadcast_def();
        let created = create_row(
            &s,
            &def,
            &serde_json::json!({
                "kind": "announcement",
                "title": "Hello",
                "message": "World",
                "email_subject": "Hi",
                "template": "broadcast/announcement.html",
                "status": "pending",
                "total": 10,
                "sent_count": 0,
                "failed_count": 0,
            }),
        )
        .await
        .unwrap();
        let id = created.get("id").and_then(|v| v.as_str()).unwrap().to_string();
        let got = get_row(&s, &def, &id).await.unwrap().expect("created row");
        assert_eq!(got.get("title").and_then(|v| v.as_str()), Some("Hello"));
        let params: HashMap<String, String> =
            [("search".to_string(), "Hello".to_string())].into_iter().collect();
        let list = list_rows(&s, &def, &params).await.unwrap();
        assert_eq!(list.get("count").and_then(|v| v.as_i64()), Some(1));
        let updated = update_row(&s, &def, &id, &serde_json::json!({"title": "Hi"}), true)
            .await
            .unwrap()
            .expect("updated row");
        assert_eq!(updated.get("title").and_then(|v| v.as_str()), Some("Hi"));
        assert!(delete_row(&s, &def, &id).await.unwrap());
        assert!(get_row(&s, &def, &id).await.unwrap().is_none());
        // Dashboard counts the model.
        let dash = dashboard(&s).await;
        assert!(dash.as_array().unwrap().iter().any(|m| m.get("model")
            .and_then(|v| v.as_str())
            == Some("broadcast.Broadcast")));
    }

    #[tokio::test]
    async fn vendor_approve_reject_flow() {
        let db = memory_db().await;
        let (s, secret) = test_state(db.clone());
        sqlx::query(
            "CREATE TABLE market_place_ticketvendor (id UUID NOT NULL PRIMARY KEY, is_verified BOOLEAN NOT NULL,
             created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, verification_status varchar(20) NULL, rejection_reason text NULL)",
        )
        .execute(&db)
        .await
        .unwrap();
        sqlx::query(
            "INSERT INTO market_place_ticketvendor (id, is_verified, created_at, updated_at)
             VALUES ('11111111-1111-1111-1111-111111111111', FALSE, '2026-01-01 00:00:00', '2026-01-01 00:00:00')",
        )
        .execute(&db)
        .await
        .unwrap();
        let staff = bearer(&secret, 1);
        let (code, _) = market_place::approve_vendor(
            State(s.clone()),
            staff.clone(),
            Path("11111111-1111-1111-1111-111111111111".to_string()),
        )
        .await;
        assert_eq!(code, StatusCode::OK);
        let (code, _) = market_place::reject_vendor(
            State(s.clone()),
            staff,
            Path("11111111-1111-1111-1111-111111111111".to_string()),
            Json(serde_json::json!({"reason": "docs"})),
        )
        .await;
        assert_eq!(code, StatusCode::OK);
        let row: (bool, Option<String>) = sqlx::query_as(
            "SELECT is_verified, verification_status FROM market_place_ticketvendor WHERE id = '11111111-1111-1111-1111-111111111111'",
        )
        .fetch_one(&db)
        .await
        .unwrap();
        assert!(!row.0);
        assert_eq!(row.1.as_deref(), Some("rejected"));
    }
}
