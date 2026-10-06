//! Clock helpers. All written timestamps are truncated to microseconds and
//! formatted `"YYYY-MM-DD HH:MM:SS.ffffff"` (fraction omitted when zero),
//! matching what Django stores in SQLite (`timezone.now()`).

use chrono::NaiveDateTime;

pub fn now_naive() -> NaiveDateTime {
    let micros = chrono::Utc::now().timestamp_micros();
    chrono::DateTime::from_timestamp_micros(micros)
        .map(|dt| dt.naive_utc())
        .unwrap_or_else(|| chrono::Utc::now().naive_utc())
}

pub fn now_str() -> String {
    format_naive(&now_naive())
}

pub fn format_naive(dt: &NaiveDateTime) -> String {
    if dt.nanosecond() == 0 {
        dt.format("%Y-%m-%d %H:%M:%S").to_string()
    } else {
        dt.format("%Y-%m-%d %H:%M:%S%.6f").to_string()
    }
}

use chrono::Timelike;

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
