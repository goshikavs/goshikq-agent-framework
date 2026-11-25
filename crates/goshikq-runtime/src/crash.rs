//! Test-only process abort and pause points. Production servers leave these unset.

use std::path::PathBuf;
use std::time::Duration;

use goshikq_protocol::{CrashBarrier, EffectCategory};
use uuid::Uuid;

/// Abort the process with status 97 when `GOSHIKQ_CRASH_AT` matches `barrier`.
/// Optional `GOSHIKQ_CRASH_RUN_ID` scopes the abort to one run.
pub fn crash_at(barrier: CrashBarrier, run_id: Uuid) {
    let wanted = match goshikq_core::env::branded("CRASH_AT") {
        Some(s) => s,
        None => return,
    };
    if CrashBarrier::parse(&wanted) != Some(barrier) {
        return;
    }
    if let Some(only) = goshikq_core::env::branded("CRASH_RUN_ID") {
        if !only.is_empty() && only != run_id.to_string() {
            return;
        }
    }
    tracing::error!(barrier = barrier.as_str(), run_id = %run_id, "GOSHIKQ_CRASH_AT: aborting process");
    std::process::exit(97);
}

/// Same as [`crash_at`], but ignored for read-only tools so barriers hit the write.
pub fn crash_at_write(barrier: CrashBarrier, run_id: Uuid, effect: EffectCategory) {
    if matches!(effect, EffectCategory::ReadOnly) {
        return;
    }
    crash_at(barrier, run_id);
}

/// Block the executor before a terminal run-row write when `GOSHIKQ_PAUSE_AT=before_terminal_write`.
///
/// Writes `{GOSHIKQ_PAUSE_DIR}/paused-{run_id}` and waits until `{dir}/release-{run_id}` appears.
/// Used to let another worker steal the lease. A missing release file stops waiting after 120s
/// so a stray env var cannot wedge a process forever.
pub async fn pause_before_terminal_write(run_id: Uuid) {
    let Some(wanted) = goshikq_core::env::branded("PAUSE_AT") else {
        return;
    };
    if wanted != "before_terminal_write" {
        return;
    }
    if let Some(only) = goshikq_core::env::branded("PAUSE_RUN_ID") {
        if !only.is_empty() && only != run_id.to_string() {
            return;
        }
    }
    let dir = goshikq_core::env::branded("PAUSE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let _ = std::fs::create_dir_all(&dir);
    let paused = dir.join(format!("paused-{run_id}"));
    let release = dir.join(format!("release-{run_id}"));
    if let Err(err) = std::fs::write(&paused, b"1") {
        tracing::error!(path = %paused.display(), error = %err, "could not write pause sentinel");
        return;
    }
    tracing::warn!(run_id = %run_id, path = %paused.display(), "GOSHIKQ_PAUSE_AT: waiting before terminal write");
    let deadline = std::time::Instant::now() + Duration::from_secs(120);
    while !release.exists() {
        if std::time::Instant::now() >= deadline {
            tracing::error!(run_id = %run_id, "pause before terminal write timed out");
            break;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}
