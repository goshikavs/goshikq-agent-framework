"""Failure injection that does not require stopping PostgreSQL.

Database-disconnect and process-crash remain in tests/crash. This file covers
invalid auth when OIDC is off (auth-none must not invent a session) and malformed
JSON on public routes.
"""

from __future__ import annotations

import httpx
import pytest

# runtime_url: session fixture in conftest.py


def test_malformed_run_body_is_rejected(runtime_url: str) -> None:
    with httpx.Client(base_url=runtime_url, timeout=10) as c:
        r = c.post("/api/v1/runs", content="{not-json", headers={"content-type": "application/json"})
        assert r.status_code in (400, 415, 422)


def test_unknown_run_is_not_found(runtime_url: str) -> None:
    with httpx.Client(base_url=runtime_url, timeout=10) as c:
        r = c.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
        assert r.status_code in (400, 404)


def test_invalid_bearer_is_ignored_in_auth_none_or_rejected(runtime_url: str) -> None:
    with httpx.Client(base_url=runtime_url, timeout=10) as c:
        r = c.get("/health", headers={"authorization": "Bearer totally-invalid"})
        assert r.status_code == 200
        r2 = c.get("/api/v1/runs", headers={"authorization": "Bearer totally-invalid"})
        assert r2.status_code in (200, 401, 403)
