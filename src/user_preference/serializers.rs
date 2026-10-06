//! Response shapes for user profiles. Mirrors
//! `user_preference/serializers.py` (`CurrentUserSerializer` with DVA info,
//! `UserPreferenceSerializer`).

use serde::Serialize;
use serde_json::{Value, json};
use utoipa::ToSchema;

use crate::accounts::models::{DvaAccount, Profile};
use crate::transactions::serializers::format_naive_lagos;

use super::models::Preference;

fn media_url(path: Option<&str>) -> Value {
    match path.filter(|p| !p.is_empty()) {
        Some(p) => Value::String(format!("/media/{p}")),
        None => Value::Null,
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct DvaInfo {
    pub dva_account_number: Option<String>,
    pub dva_account_name: Option<String>,
    pub bank_name: String,
    pub bank_slug: String,
    pub bank_id: Option<i64>,
    pub customer_code: String,
    pub active: bool,
}

impl DvaInfo {
    pub fn from_row(d: &DvaAccount) -> Self {
        Self {
            dva_account_number: d.dva_account_number.clone(),
            dva_account_name: d.dva_account_name.clone(),
            bank_name: d.bank_name.clone(),
            bank_slug: d.bank_slug.clone(),
            bank_id: d.bank_id,
            customer_code: d.customer_code.clone(),
            active: d.active,
        }
    }
}

pub fn current_user_json(
    user: &Profile,
    dva: Option<&DvaAccount>,
    preference: &Preference,
) -> Value {
    json!({
        "id": user.id,
        "other_names": user.other_names,
        "email": user.email,
        "phone": user.phone,
        "surname": user.surname,
        "pin_is_set": user.pin_is_set,
        "image": media_url(user.image.as_deref()),
        "is_staff": user.is_staff,
        "is_admin": user.is_admin,
        "referral_code": user.referral_code,
        "created_on": format_naive_lagos(&user.created_on),
        "has_DVA": user.has_dva,
        "dva_account": dva.map(DvaInfo::from_row).map(|d| serde_json::to_value(&d).unwrap_or(Value::Null)),
        "preference": preference_json(preference),
    })
}

pub fn preference_json(preference: &Preference) -> Value {
    json!({
        "image": media_url(preference.image.as_deref()),
        "nickname": preference.nickname,
        "gender": preference.gender,
        "date_of_birth": preference.date_of_birth.map(|d| d.to_string()),
        "country": preference.country,
        "state": preference.state,
        "city": preference.city,
        "street_address": preference.street_address,
        "landmark": preference.landmark,
        "postal_code": preference.postal_code,
        "updated_on": format_naive_lagos(&preference.updated_on),
    })
}

#[derive(Debug, serde::Deserialize, ToSchema)]
pub struct UpdatePreferenceBody {
    pub phone: Option<String>,
    pub image: Option<String>,
    pub nickname: Option<String>,
    pub gender: Option<String>,
    pub date_of_birth: Option<String>,
    pub country: Option<String>,
    pub state: Option<String>,
    pub city: Option<String>,
    pub street_address: Option<String>,
    pub landmark: Option<String>,
    pub postal_code: Option<String>,
}
