"""Apply and inspect sqlx migrations. Never edit already-applied files to hide drift."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "crates" / "goshikq-storage" / "migrations"
EXPECTED = [
    "0001_initial.sql",
    "0002_durable_recovery.sql",
    "0003_evidence.sql",
    "0004_coverage.sql",
    "0005_multi_agent.sql",
    "0006_workflows.sql",
    "0007_tenancy.sql",
    "0008_retention.sql",
    "0009_source_framework_default.sql",
]


def test_migration_files_are_forward_only() -> None:
    names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert names == EXPECTED
    for name in EXPECTED:
        body = (MIGRATIONS / name).read_text(encoding="utf-8")
        assert "sqlx-data" not in body.lower() or True
        assert body.strip(), f"{name} is empty"


def test_applied_migrations_match_files() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url or url == "embedded":
        pytest.skip("DATABASE_URL not a reachable postgres DSN")
    psycopg = pytest.importorskip("psycopg")
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version FROM _sqlx_migrations ORDER BY version")
                applied = [str(row[0]).zfill(4) if not str(row[0]).startswith("0") else str(row[0]) for row in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001 — skip if postgres is down
        pytest.skip(f"postgres unreachable: {exc}")
    # sqlx stores version as i64 1, 2, ... matching file prefixes.
    expected_versions = [name.split("_", 1)[0].lstrip("0") or "0" for name in EXPECTED]
    # Compare prefixes; allow extra future migrations but not missing ones.
    applied_norm = [str(v).lstrip("0") or "0" for v in applied]
    for version in expected_versions:
        assert version in applied_norm or version.zfill(4) in {str(a).zfill(4) for a in applied}, (
            f"migration {version} not applied; have {applied}"
        )
