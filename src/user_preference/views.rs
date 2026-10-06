//! Profile endpoints. Mirrors `user_preference/views.py::CurrentUserView`
//! (GET + PATCH `user/`, JSON or multipart) and `CheckUser`
//! (`GET check/<email>/`, public, `name` always null like Django).

use std::collections::HashMap;

use axum::{
    Json,
    extract::{FromRequest, Multipart, Path, Request, State},
    http::{HeaderMap, StatusCode, header::CONTENT_TYPE},
};
use serde_json::{Value, json};

use crate::accounts::models as accounts_models;
use crate::auth::extractor::auth_user;
use crate::error::AppError;
use crate::state::AppState;

use super::models as pref_models;
use super::serializers as pref_serializers;

type Resp = (StatusCode, Json<Value>);

#[utoipa::path(
    get,
    path = "/user_preference/user/",
    tag = "User Profile",
    summary = "Get current user profile",
    description = "Return the authenticated user's profile details, including saved preferences and DVA info.",
    responses((status = 200, description = "Profile returned"), (status = 400, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn current_user(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Resp, AppError> {
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::bad_request("An error occurred"))?;
    let now = crate::time::now_str();
    let preference = pref_models::get_or_create(&s.db, user.id, &now).await?;
    let dva = if user.has_dva {
        accounts_models::find_dva_by_user(&s.db, user.id)
            .await
            .unwrap_or(None)
    } else {
        None
    };
    Ok((
        StatusCode::OK,
        Json(pref_serializers::current_user_json(
            &user,
            dva.as_ref(),
            &preference,
        )),
    ))
}

fn apply_field(
    updates: &mut HashMap<String, Option<String>>,
    name: &str,
    value: Option<&str>,
    max: usize,
    choices: Option<&[&str]>,
) {
    let Some(v) = value else {
        return;
    };
    if v.chars().count() > max {
        return;
    }
    if let Some(list) = choices {
        if !v.is_empty() && !list.contains(&v) {
            return;
        }
    }
    updates.insert(name.to_string(), Some(v.to_string()));
}

fn apply_date(updates: &mut HashMap<String, Option<String>>, value: Option<&str>) {
    if let Some(v) = value {
        if chrono::NaiveDate::parse_from_str(v, "%Y-%m-%d").is_ok() {
            updates.insert("date_of_birth".to_string(), Some(v.to_string()));
        }
    }
}

const IMAGE_EXTS: &[&str] = &["jpg", "jpeg", "png", "gif", "webp", "bmp"];

async fn store_upload(
    media_root: &str,
    filename: &str,
    bytes: &[u8],
) -> Option<String> {
    if bytes.is_empty() || bytes.len() > 20 * 1024 * 1024 {
        return None;
    }
    let ext = filename
        .rsplit('.')
        .next()
        .unwrap_or("")
        .to_lowercase();
    if ext.is_empty()
        || ext.len() > 5
        || !ext.chars().all(|c| c.is_ascii_alphanumeric())
        || !IMAGE_EXTS.contains(&ext.as_str())
    {
        return None;
    }
    let stored = format!("profiles/{}.{}", uuid::Uuid::new_v4().simple(), ext);
    let path = std::path::Path::new(media_root).join(&stored);
    if let Some(parent) = path.parent() {
        if tokio::fs::create_dir_all(parent).await.is_err() {
            return None;
        }
    }
    if tokio::fs::write(&path, bytes).await.is_err() {
        return None;
    }
    Some(stored)
}

#[utoipa::path(
    patch,
    path = "/user_preference/user/",
    tag = "User Profile",
    summary = "Update current user profile",
    description = "Update phone and/or preference fields and/or profile image (JSON or multipart). Invalid fields are ignored.",
    responses((status = 200, description = "Profile updated"), (status = 400, description = "Failed")),
    security(("bearer" = [])),
)]
pub async fn update_user(
    State(s): State<AppState>,
    req: Request,
) -> Result<Resp, AppError> {
    let headers = req.headers().clone();
    let is_multipart = headers
        .get(CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .map(|ct| ct.starts_with("multipart/"))
        .unwrap_or(false);
    let user = auth_user(State(s.clone()), headers)
        .await
        .map_err(|_| AppError::bad_request("An error occurred"))?;

    // Accept JSON or multipart, like DRF's parser classes.
    let mut fields: HashMap<String, String> = HashMap::new();
    let mut upload: Option<(String, Vec<u8>)> = None;
    if is_multipart {
        let mut multipart = Multipart::from_request(req, &s)
            .await
            .map_err(|_| AppError::bad_request("An error occurred"))?;
        while let Ok(Some(field)) = multipart.next_field().await {
            let name = field.name().unwrap_or("").to_string();
            let filename = field.file_name().map(|f| f.to_string());
            match field.bytes().await {
                Ok(bytes) => {
                    if let Some(fname) = filename {
                        if name == "image" && upload.is_none() {
                            upload = Some((fname, bytes.to_vec()));
                        }
                    } else if let Ok(text) = String::from_utf8(bytes.to_vec()) {
                        fields.insert(name, text);
                    }
                }
                Err(_) => continue,
            }
        }
    } else {
        let body = axum::body::to_bytes(req.into_body(), 20 * 1024 * 1024)
            .await
            .unwrap_or_default();
        if !body.is_empty() {
            if let Ok(Value::Object(map)) = serde_json::from_slice::<Value>(&body) {
                for (k, v) in map {
                    let text = match &v {
                        Value::String(s) => s.clone(),
                        Value::Number(n) => n.to_string(),
                        _ => continue,
                    };
                    fields.insert(k, text);
                }
            }
        }
    }

    if let Some(phone) = fields.get("phone") {
        let _ = sqlx::query("UPDATE accounts_profile SET phone = ? WHERE id = ?")
            .bind(phone)
            .bind(user.id)
            .execute(&s.db)
            .await;
    }

    let now = crate::time::now_str();
    let mut preference = pref_models::get_or_create(&s.db, user.id, &now).await?;

    let mut updates: HashMap<String, Option<String>> = HashMap::new();
    let get = |k: &str| fields.get(k).map(|v| v.as_str());
    apply_field(&mut updates, "nickname", get("nickname"), 50, None);
    apply_field(
        &mut updates,
        "gender",
        get("gender"),
        20,
        Some(&["male", "female", "others"]),
    );
    apply_date(&mut updates, get("date_of_birth"));
    apply_field(&mut updates, "country", get("country"), 50, None);
    apply_field(&mut updates, "state", get("state"), 20, None);
    apply_field(&mut updates, "city", get("city"), 20, None);
    apply_field(&mut updates, "street_address", get("street_address"), 100, None);
    apply_field(&mut updates, "landmark", get("landmark"), 50, None);
    apply_field(&mut updates, "postal_code", get("postal_code"), 10, None);

    if let Some((filename, bytes)) = upload {
        if let Some(stored) = store_upload(&s.config.media_root, &filename, &bytes).await
        {
            updates.insert("image".to_string(), Some(stored));
        }
    }

    if !updates.is_empty() {
        let mut set: Vec<String> = updates.keys().map(|k| format!("{k} = ?")).collect();
        set.push("updated_on = ?".to_string());
        let sql = format!(
            "UPDATE user_preference_updateusermodel SET {} WHERE user_id = ?",
            set.join(", ")
        );
        let mut q = sqlx::query(&sql);
        for k in updates.keys() {
            q = q.bind(updates.get(k).unwrap().as_deref());
        }
        let now2 = crate::time::now_str();
        q = q.bind(&now2).bind(user.id);
        let _ = q.execute(&s.db).await;
        preference = pref_models::get_or_create(&s.db, user.id, &now2).await?;
    }

    // Fresh profile row for the response (phone may have changed).
    let user = crate::auth::extractor::get_profile(&s.db, user.id).await?;
    let image = user.image.as_deref().map(|p| format!("/media/{p}"));
    Ok((
        StatusCode::OK,
        Json(json!({
            "message": "Profile updated successfully",
            "phone": user.phone,
            "image": image,
            "preference": pref_serializers::preference_json(&preference),
        })),
    ))
}

#[utoipa::path(
    get,
    path = "/user_preference/check/{email}/",
    tag = "User Profile",
    summary = "Check user verification status",
    description = "Check whether a user with the given email exists and is verified. Public.",
    params(("email" = String, Path, description = "Email of the user to check")),
    responses(
        (status = 200, description = "User is verified"),
        (status = 404, description = "User is not verified"),
    ),
)]
pub async fn check_user(
    State(s): State<AppState>,
    Path(email): Path<String>,
) -> Result<Resp, AppError> {
    let row: Option<(Option<String>,)> = sqlx::query_as(
        "SELECT surname FROM accounts_profile WHERE email = ? AND email_verified = 1",
    )
    .bind(&email)
    .fetch_optional(&s.db)
    .await?;
    match row {
        // `username` does not exist on the profile: Django's getattr
        // returns None, so `name` is always null here.
        Some((surname,)) => Ok((
            StatusCode::OK,
            Json(json!({
                "state": true,
                "message": "User is verified",
                "data": {"name": Value::Null, "surname": surname},
            })),
        )),
        None => Ok((
            StatusCode::NOT_FOUND,
            Json(json!({"state": false, "message": "User is not verified"})),
        )),
    }
}
