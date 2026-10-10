//! Clock helpers. All written timestamps are truncated to microseconds and
//! formatted `"YYYY-MM-DD HH:MM:SS.ffffff"` (fraction omitted when zero),
//! matching what Django stores (`timezone.now()`, UTC wall-clock).

use chrono::{NaiveDateTime, Timelike};

/// Naive UTC wall-clock timestamp that decodes from Postgres `timestamptz`.
///
/// sqlx will not decode `timestamptz` into `chrono::NaiveDateTime` (it
/// demands `TIMESTAMP`), while our Django-schema columns are all
/// `timestamptz` holding UTC instants. This wrapper reads the instant and
/// exposes the naive UTC wall time, dereferencing to `NaiveDateTime` so all
/// existing formatting/comparison code keeps working unchanged.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, serde::Serialize)]
#[serde(transparent)]
pub struct NaiveUtc(pub NaiveDateTime);

impl std::ops::Deref for NaiveUtc {
    type Target = NaiveDateTime;
    fn deref(&self) -> &NaiveDateTime {
        &self.0
    }
}

impl std::fmt::Display for NaiveUtc {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.0.fmt(f)
    }
}

impl From<NaiveDateTime> for NaiveUtc {
    fn from(dt: NaiveDateTime) -> Self {
        Self(dt)
    }
}

impl std::ops::Add<chrono::Duration> for NaiveUtc {
    type Output = NaiveDateTime;
    fn add(self, rhs: chrono::Duration) -> NaiveDateTime {
        self.0 + rhs
    }
}

impl std::ops::Sub<NaiveUtc> for NaiveUtc {
    type Output = chrono::Duration;
    fn sub(self, rhs: NaiveUtc) -> chrono::Duration {
        self.0 - rhs.0
    }
}

impl sqlx::Type<sqlx::Postgres> for NaiveUtc {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        <chrono::DateTime<chrono::Utc> as sqlx::Type<sqlx::Postgres>>::type_info()
    }
}

impl<'r> sqlx::Decode<'r, sqlx::Postgres> for NaiveUtc {
    fn decode(
        value: sqlx::postgres::PgValueRef<'r>,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let dt = <chrono::DateTime<chrono::Utc> as sqlx::Decode<'r, sqlx::Postgres>>::decode(value)?;
        Ok(Self(dt.naive_utc()))
    }
}

pub fn now_naive() -> NaiveDateTime {
    let micros = chrono::Utc::now().timestamp_micros();
    chrono::DateTime::from_timestamp_micros(micros)
        .map(|dt| dt.naive_utc())
        .unwrap_or_else(|| chrono::Utc::now().naive_utc())
}

pub fn now_str() -> String {
    format_naive(&now_naive())
}

/// Parse a stored datetime string into naive UTC: accepts our written
/// `"YYYY-MM-DD HH:MM:SS[.ffffff]"` form as well as Postgres
/// `timestamptz` text (`"...[.ffffff]+00"`, `"...Z"`), which is what
/// `CAST(ts_col AS TEXT)` yields under `SET TIME ZONE 'UTC'`.
pub fn parse_stored_dt(raw: &str) -> Option<NaiveDateTime> {
    let s = raw.trim();
    let s = s.strip_suffix(['Z', 'z']).unwrap_or(s);
    let core = if let Some(i) = s.rfind(|c| c == '+' || c == '-') {
        // A trailing numeric offset belongs to the time part (past char 10).
        if i > 10 {
            &s[..i]
        } else {
            s
        }
    } else {
        s
    };
    chrono::NaiveDateTime::parse_from_str(core, "%Y-%m-%d %H:%M:%S%.f")
        .or_else(|_| chrono::NaiveDateTime::parse_from_str(core, "%Y-%m-%d %H:%M:%S"))
        .ok()
}

pub fn format_naive(dt: &NaiveDateTime) -> String {
    if dt.nanosecond() == 0 {
        dt.format("%Y-%m-%d %H:%M:%S").to_string()
    } else {
        dt.format("%Y-%m-%d %H:%M:%S%.6f").to_string()
    }
}

/// Bind wrapper for timestamp strings (`"YYYY-MM-DD HH:MM:SS[.ffffff]"` or
/// `"YYYY-MM-DD"`): encodes them as UTC `timestamptz`.
///
/// Needed because sqlx sends plain `String` binds as `text`, and Postgres
/// has no implicit `text` → `timestamptz` cast — while our Django-schema
/// columns are `timestamptz`. All stored values are UTC wall-clock, matching
/// the `SET TIME ZONE 'UTC'` in `db::connect`.
pub struct Ts<T>(pub T);

impl<T: AsRef<str>> sqlx::Type<sqlx::Postgres> for Ts<T> {
    fn type_info() -> sqlx::postgres::PgTypeInfo {
        sqlx::postgres::PgTypeInfo::with_name("timestamptz")
    }
}

impl<'q, T: AsRef<str>> sqlx::Encode<'q, sqlx::Postgres> for Ts<T> {
    fn encode_by_ref(
        &self,
        buf: &mut sqlx::postgres::PgArgumentBuffer,
    ) -> Result<sqlx::encode::IsNull, Box<dyn std::error::Error + Send + Sync>> {
        let raw = self.0.as_ref();
        let naive = parse_stored_dt(raw)
            .or_else(|| {
                chrono::NaiveDate::parse_from_str(raw.trim(), "%Y-%m-%d")
                    .ok()
                    .and_then(|d| d.and_hms_opt(0, 0, 0))
            })
            .ok_or_else(|| -> Box<dyn std::error::Error + Send + Sync> {
                format!("bad timestamp for Ts bind: {raw}").into()
            })?;
        // Binary timestamptz format: int64 big-endian microseconds since the
        // POSTGRES epoch (2000-01-01), not the Unix epoch. Values are UTC
        // wall-clock by convention here.
        const PG_EPOCH_MICROS: i64 = 946_684_800_000_000;
        let micros = naive.and_utc().timestamp_micros() - PG_EPOCH_MICROS;
        buf.extend_from_slice(&micros.to_be_bytes());
        Ok(sqlx::encode::IsNull::No)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_django_storage_format() {
        let s = now_str();
        assert!(
            s.len() == 19 || s.len() == 26,
            "expected 'YYYY-MM-DD HH:MM:SS[.ffffff]', got {s}"
        );
        // microsecond truncation: at most 6 fractional digits
        if let Some(frac) = s.split(' ').nth(1).and_then(|t| t.split('.').nth(1)) {
            assert!(frac.len() <= 6, "{s}");
        }
    }
}
