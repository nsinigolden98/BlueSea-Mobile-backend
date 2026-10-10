//! Database pool + connection setup. Postgres only.
//!
//! All timestamps are stored as UTC wall-clock values (Django writes naive
//! UTC into `timestamptz` columns). Every pooled connection runs
//! `SET TIME ZONE 'UTC'` on checkout so naive timestamp strings are always
//! interpreted as UTC regardless of server locale.

use sqlx::Executor;
use sqlx::postgres::{PgConnectOptions, PgPoolOptions};

pub type DbPool = sqlx::PgPool;

pub async fn connect(url: &str) -> Result<DbPool, sqlx::Error> {
    let options: PgConnectOptions = url.parse()?;
    PgPoolOptions::new()
        .max_connections(10)
        .after_connect(|conn, _meta| {
            Box::pin(async move {
                conn.execute("SET TIME ZONE 'UTC'").await?;
                Ok(())
            })
        })
        .connect_with(options)
        .await
}

#[cfg(test)]
pub mod test_support {
    use super::*;

    fn test_base_url() -> String {
        // Tests share the single DATABASE_URL (default: the test database).
        // Each test still gets an isolated scratch database; your real
        // tables are never touched. `.env` is loaded so plain `cargo test`
        // works; an exported DATABASE_URL still wins.
        crate::settings::load_dotenv_literal();
        std::env::var("DATABASE_URL").unwrap_or_else(|_| {
            "postgres://postgres:postgres@localhost:5432/bluesea_test".to_string()
        })
    }

    static COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

    /// Create an isolated scratch database, run `ddl` statements in it, and
    /// return a pool. Mirrors the old per-test in-memory SQLite databases.
    /// Databases are named `test_<pid>_<n>`; stale ones can be dropped
    /// manually (`DROP DATABASE`) — they hold no production data.
    pub async fn fresh_db(ddl: &[&str]) -> DbPool {
        let base = test_base_url();
        let n = COUNTER.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        let name = format!("test_{}_{}", std::process::id(), n);
        let admin_url = if let Some((head, _)) = base.rsplit_once('/') {
            format!("{head}/postgres")
        } else {
            "postgres://postgres:postgres@localhost:5432/postgres".to_string()
        };
        let admin = connect(&admin_url).await.expect("test admin connect");
        sqlx::query(&format!(r#"CREATE DATABASE "{name}""#))
            .execute(&admin)
            .await
            .expect("test create database");
        admin.close().await;
        let url = if let Some((head, _)) = base.rsplit_once('/') {
            format!("{head}/{name}")
        } else {
            unreachable!()
        };
        let pool = connect(&url).await.expect("test pool connect");
        for stmt in ddl {
            sqlx::query(stmt)
                .execute(&pool)
                .await
                .unwrap_or_else(|e| panic!("test ddl failed: {e}\n{stmt}"));
        }
        pool
    }
}
