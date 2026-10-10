//! User preference rows. Mirrors
//! `user_preference/models.py::UpdateUserModel`.

use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct Preference {
    pub id: i64,
    pub image: Option<String>,
    pub nickname: Option<String>,
    pub gender: Option<String>,
    pub date_of_birth: Option<chrono::NaiveDate>,
    pub country: Option<String>,
    pub state: Option<String>,
    pub city: Option<String>,
    pub street_address: Option<String>,
    pub landmark: Option<String>,
    pub postal_code: Option<String>,
    pub updated_on: crate::time::NaiveUtc,
    pub user_id: i64,
}

pub async fn get_or_create(
    db: &sqlx::PgPool,
    user_id: i64,
    now: &str,
) -> Result<Preference, sqlx::Error> {
    if let Some(p) = sqlx::query_as::<_, Preference>(
        "SELECT id, image, nickname, gender, date_of_birth, country, state, city,
                street_address, landmark, postal_code, updated_on, user_id
         FROM user_preference_updateusermodel WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_optional(db)
    .await?
    {
        return Ok(p);
    }
    sqlx::query(
        "INSERT INTO user_preference_updateusermodel (image, user_id, date_of_birth, country, state, city,
                street_address, landmark, postal_code, gender, nickname, updated_on)
         VALUES (NULL, $1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, $2)",
    )
    .bind(user_id)
    .bind(crate::time::Ts(&now))
    .execute(db)
    .await?;
    sqlx::query_as::<_, Preference>(
        "SELECT id, image, nickname, gender, date_of_birth, country, state, city,
                street_address, landmark, postal_code, updated_on, user_id
         FROM user_preference_updateusermodel WHERE user_id = $1",
    )
    .bind(user_id)
    .fetch_one(db)
    .await
}
