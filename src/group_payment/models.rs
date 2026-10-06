//! Group rows. Mirrors `group_payment/models.py`:
//! UUID PKs stored dashless (char(32)), 6-char uppercase join codes.

use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct GroupRow {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub created_by_id: Option<i64>,
    pub service_type: String,
    pub sub_number: String,
    pub plan: String,
    pub plan_type: Option<String>,
    pub target_amount: i64,
    pub current_amount: i64,
    pub status: String,
    pub active: bool,
    pub invite_members: String,
    pub join_code: String,
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
}

const GROUP_COLS: &str = "id, name, description, created_by_id, service_type, sub_number, plan,
        plan_type, target_amount, current_amount, status, active, invite_members, join_code,
        created_at, updated_at";

#[derive(Debug, Clone, FromRow)]
pub struct MemberRow {
    pub id: i64,
    pub role: String,
    pub joined_at: chrono::NaiveDateTime,
    pub group_id: String,
    pub user_id: i64,
    pub locked_amount: i64,
    pub paid_amount: i64,
    pub payment_status: String,
}

pub fn generate_join_code() -> String {
    let bytes: [u8; 3] = rand::random();
    hex::encode(bytes).to_uppercase()
}

pub async fn group_by_id(
    db: &sqlx::SqlitePool,
    id_hex: &str,
) -> Result<Option<GroupRow>, sqlx::Error> {
    sqlx::query_as::<_, GroupRow>(&format!(
        "SELECT {GROUP_COLS} FROM group_payment_group WHERE id = ?"
    ))
    .bind(id_hex)
    .fetch_optional(db)
    .await
}

pub async fn group_by_join_code(
    db: &sqlx::SqlitePool,
    join_code: &str,
) -> Result<Option<GroupRow>, sqlx::Error> {
    sqlx::query_as::<_, GroupRow>(&format!(
        "SELECT {GROUP_COLS} FROM group_payment_group WHERE lower(join_code) = lower(?) AND active = 1"
    ))
    .bind(join_code)
    .fetch_optional(db)
    .await
}

pub async fn members_of(
    db: &sqlx::SqlitePool,
    group_id: &str,
) -> Result<Vec<MemberRow>, sqlx::Error> {
    sqlx::query_as::<_, MemberRow>(
        "SELECT id, role, joined_at, group_id, user_id, locked_amount, paid_amount, payment_status
         FROM group_payment_groupmember WHERE group_id = ? ORDER BY id",
    )
    .bind(group_id)
    .fetch_all(db)
    .await
}

pub async fn member_role(
    db: &sqlx::SqlitePool,
    group_id: &str,
    user_id: i64,
    roles: &[&str],
) -> Result<Option<MemberRow>, sqlx::Error> {
    let placeholders = roles.iter().map(|_| "?").collect::<Vec<_>>().join(",");
    let sql = format!(
        "SELECT id, role, joined_at, group_id, user_id, locked_amount, paid_amount, payment_status
         FROM group_payment_groupmember WHERE group_id = ? AND user_id = ? AND role IN ({placeholders})"
    );
    let mut q = sqlx::query_as::<_, MemberRow>(&sql).bind(group_id).bind(user_id);
    for r in roles {
        q = q.bind(*r);
    }
    q.fetch_optional(db).await
}

pub async fn member_counts(
    db: &sqlx::SqlitePool,
    group_id: &str,
) -> Result<(i64, i64, i64), sqlx::Error> {
    let row: (i64, i64, i64) = sqlx::query_as(
        "SELECT COUNT(*),
                SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END),
                SUM(CASE WHEN payment_status = 'pending' THEN 1 ELSE 0 END)
         FROM group_payment_groupmember WHERE group_id = ?",
    )
    .bind(group_id)
    .fetch_optional(db)
    .await?
    .unwrap_or((0, 0, 0));
    Ok(row)
}

pub async fn groups_of_user(
    db: &sqlx::SqlitePool,
    user_id: i64,
) -> Result<Vec<(MemberRow, GroupRow)>, sqlx::Error> {
    let memberships: Vec<MemberRow> = sqlx::query_as(
        "SELECT id, role, joined_at, group_id, user_id, locked_amount, paid_amount, payment_status
         FROM group_payment_groupmember WHERE user_id = ? ORDER BY id",
    )
    .bind(user_id)
    .fetch_all(db)
    .await?;
    let mut out = Vec::new();
    for m in memberships {
        if let Some(g) = group_by_id(db, &m.group_id).await? {
            out.push((m, g));
        }
    }
    Ok(out)
}
