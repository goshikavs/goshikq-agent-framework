//! Local-development PostgreSQL that does not require Docker.
//!
//! When `DATABASE_URL=embedded` (the default in `.env.example`), goshikq-server downloads
//! a Theseus PostgreSQL distribution once, stores data under `.goshikq/postgres`, and
//! listens on loopback. Production deployments must set a real `DATABASE_URL`.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use postgresql_embedded::{PostgreSQL, Settings};

/// Owns the child postgres process for the lifetime of the server.
pub struct EmbeddedPostgres {
    inner: PostgreSQL,
    pub url: String,
}

impl EmbeddedPostgres {
    pub async fn start(data_dir: PathBuf) -> Result<Self> {
        std::fs::create_dir_all(&data_dir)
            .with_context(|| format!("creating {}", data_dir.display()))?;
        let mut settings = Settings::default();
        settings.host = "127.0.0.1".into();
        settings.port = goshikq_core::env::branded("EMBEDDED_PG_PORT")
            .and_then(|s| s.parse().ok())
            .unwrap_or(55432);
        // initdb creates the bootstrap superuser `postgres`. New clusters use
        // database/password `goshikq`; a pre-rebrand `.axiom/postgres` cluster keeps `axiom`.
        let (password, dbname) = cluster_credentials(&data_dir);
        settings.username = postgresql_embedded::BOOTSTRAP_SUPERUSER.into();
        settings.password = password.into();
        settings.temporary = false;
        settings.timeout = Some(std::time::Duration::from_secs(
            goshikq_core::env::branded("EMBEDDED_PG_TIMEOUT_SECS")
                .and_then(|s| s.parse().ok())
                .unwrap_or(180),
        ));
        settings.data_dir = data_dir.join("data");
        settings.installation_dir = data_dir.join("install");
        settings.password_file = data_dir.join(".pgpass");
        tracing::info!(
            data_dir = %settings.data_dir.display(),
            port = settings.port,
            "starting embedded PostgreSQL (first run downloads binaries into the cache)"
        );
        let mut inner = PostgreSQL::new(settings);
        inner
            .setup()
            .await
            .context("downloading/installing embedded PostgreSQL")?;
        // sqlx always sends startup parameter TimeZone=UTC. Theseus Unix
        // builds often use the OS zoneinfo, which may omit UTC (Ubuntu 26.04
        // without tzdata-legacy) or ship a TZif revision PostgreSQL rejects.
        // Seed a known-good UTC file into the install tree before start.
        seed_utc_timezone(inner.settings().installation_dir.as_path());
        inner
            .start()
            .await
            .context("starting embedded PostgreSQL")?;
        if !inner.database_exists(dbname).await.unwrap_or(false) {
            inner
                .create_database(dbname)
                .await
                .with_context(|| format!("creating database `{dbname}`"))?;
        }
        let s = inner.settings();
        let url = format!(
            "postgres://{}:{}@{}:{}/{dbname}",
            s.username, s.password, s.host, s.port
        );
        tracing::info!(url = %redact_url(&url), "embedded PostgreSQL ready");
        Ok(EmbeddedPostgres { inner, url })
    }
}

impl Drop for EmbeddedPostgres {
    fn drop(&mut self) {
        // Best-effort; process exit also tears the child down.
        let _ = self.inner;
    }
}

fn redact_url(url: &str) -> String {
    if let Some(at) = url.find('@') {
        if let Some(scheme) = url.find("://") {
            return format!("{}://***@{}", &url[..scheme], &url[at + 1..]);
        }
    }
    url.to_string()
}

pub fn wants_embedded(database_url: &str) -> bool {
    let v = database_url.trim();
    v.eq_ignore_ascii_case("embedded")
        || v.eq_ignore_ascii_case("goshikq-embedded")
        || v.eq_ignore_ascii_case("axiom-embedded")
        || v.starts_with("embedded:")
}

pub fn default_data_dir() -> PathBuf {
    if let Some(p) = goshikq_core::env::branded("EMBEDDED_PG_DIR") {
        return PathBuf::from(p);
    }
    // Do not silently reuse a pre-rebrand `.axiom/postgres` cluster. Those
    // directories can contain modified sqlx checksums. Operators who still
    // need the old files must set GOSHIKQ_EMBEDDED_PG_DIR explicitly.
    PathBuf::from(".goshikq/postgres")
}

fn cluster_credentials(data_dir: &std::path::Path) -> (&'static str, &'static str) {
    if data_dir.to_string_lossy().contains(".axiom") {
        ("axiom", "axiom")
    } else {
        ("goshikq", "goshikq")
    }
}

/// Minimal TZif version 2 UTC (utoff 0, POSIX `UTC0`). PostgreSQL accepts this
/// when the host Olson database is missing or too new.
const UTC_TZIF: &[u8] = include_bytes!("utc.tzif");

fn seed_utc_timezone(install_dir: &Path) {
    let mut dirs = vec![
        install_dir.join("share/timezone"),
        install_dir.join("share/postgresql/timezone"),
        install_dir.join("share/pgsql/timezone"),
    ];
    if let Some(system) = system_tzdata_dir(install_dir) {
        dirs.push(system);
    }
    for dir in dirs {
        let Some(parent) = dir.parent() else {
            continue;
        };
        if !dir.exists() && !parent.exists() {
            continue;
        }
        if let Err(err) = std::fs::create_dir_all(&dir) {
            tracing::debug!(path = %dir.display(), error = %err, "skip timezone seed; cannot create directory");
            continue;
        }
        for name in ["UTC", "GMT", "Etc/UTC", "Etc/GMT"] {
            let path = dir.join(name);
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            if let Err(err) = std::fs::write(&path, UTC_TZIF) {
                tracing::debug!(path = %path.display(), error = %err, "could not seed UTC timezone file");
            }
        }
    }
}

fn system_tzdata_dir(install_dir: &Path) -> Option<PathBuf> {
    let bin = if cfg!(windows) {
        "pg_config.exe"
    } else {
        "pg_config"
    };
    let out = std::process::Command::new(install_dir.join("bin").join(bin))
        .arg("--configure")
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    for part in text.split_whitespace() {
        if let Some(path) = part
            .strip_prefix("--with-system-tzdata=")
            .map(|p| p.trim_matches('"'))
        {
            if !path.is_empty() {
                return Some(PathBuf::from(path));
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn utc_tzif_looks_like_tzif2() {
        assert!(UTC_TZIF.starts_with(b"TZif2"));
        assert!(UTC_TZIF.ends_with(b"\nUTC0\n"));
    }

    #[test]
    fn seed_utc_writes_olson_names() {
        let tmp = std::env::temp_dir().join(format!("goshikq-tz-{}", std::process::id()));
        let share = tmp.join("share");
        std::fs::create_dir_all(&share).unwrap();
        seed_utc_timezone(&tmp);
        let utc = tmp.join("share/timezone/UTC");
        assert_eq!(std::fs::read(&utc).unwrap(), UTC_TZIF);
        let _ = std::fs::remove_dir_all(&tmp);
    }
}
