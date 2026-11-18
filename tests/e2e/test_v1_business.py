"""Live v1.0 business scenarios against a real goshikq-server.

Happy-path bank/enterprise runs wait on human approval; these tests approve via API.
Travel never_confirms must not become VERIFIED.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import time
from pathlib import Path

import httpx
import pytest

# runtime_url: session fixture in conftest.py

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))


def _load(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _approve_named(url: str, agent_name: str, timeout: float = 40.0) -> dict:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=15) as client:
        while time.monotonic() < deadline:
            r = await client.get(f"{url}/api/v1/approvals?status=pending")
            if r.status_code == 200:
                items = r.json().get("items") or []
                items = [i for i in items if i.get("agent_name") == agent_name]
                if items:
                    item = items[0]
                    dec = await client.post(
                        f"{url}/api/v1/approvals/{item['id']}/decision",
                        json={"decision": "approve", "reason": "v1-e2e"},
                        headers={"x-goshikq-actor": "v1-e2e"},
                    )
                    assert dec.status_code < 300, dec.text
                    return item
            await asyncio.sleep(0.25)
    raise TimeoutError(f"no pending approval for {agent_name}")


def test_bank_happy_path_verified_after_approval(runtime_url: str) -> None:
    asyncio.run(_bank_happy(runtime_url))


async def _bank_happy(url: str) -> None:
    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    bank = _load("bank_account_update_main", ROOT / "examples" / "bank-account-update" / "main.py")
    task = asyncio.create_task(bank.run_once("none"))
    await _approve_named(url, "bank_agent")
    code = await asyncio.wait_for(task, timeout=90)
    assert code == 0
    assert bank.BANK.accounts["ACCT-1"].core_status == "applied"
    assert bank.BANK.accounts["ACCT-1"].routing == bank.NEW_ROUTING


def test_bank_stale_version_does_not_apply(runtime_url: str) -> None:
    asyncio.run(_bank_stale(runtime_url))


async def _wait_pending(url: str, agent_name: str, timeout: float = 40.0) -> dict:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=15) as client:
        while time.monotonic() < deadline:
            r = await client.get(f"{url}/api/v1/approvals?status=pending")
            if r.status_code == 200:
                items = [i for i in (r.json().get("items") or []) if i.get("agent_name") == agent_name]
                if items:
                    return items[0]
            await asyncio.sleep(0.25)
    raise TimeoutError(f"no pending approval for {agent_name}")


async def _bank_stale(url: str) -> None:
    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    bank = _load("bank_account_update_stale", ROOT / "examples" / "bank-account-update" / "main.py")
    task = asyncio.create_task(bank.run_once("none"))
    pending = await _wait_pending(url, "bank_agent")
    bank.BANK.bump_version("ACCT-1")
    async with httpx.AsyncClient(timeout=20) as client:
        dec = await client.post(
            f"{url}/api/v1/approvals/{pending['id']}/decision",
            json={"decision": "approve", "reason": "stale-version"},
            headers={"x-goshikq-actor": "v1-e2e"},
        )
        assert dec.status_code < 300, dec.text
    code = await asyncio.wait_for(task, timeout=90)
    assert bank.BANK.accounts["ACCT-1"].routing == "021000021"
    assert code != 0


def test_travel_never_confirms_is_not_verified(runtime_url: str) -> None:
    asyncio.run(_travel_pending(runtime_url))


async def _travel_pending(url: str) -> None:
    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    travel = _load("travel_booking_main", ROOT / "examples" / "travel-booking" / "main.py")
    code = await asyncio.wait_for(travel.run_once("never_confirms"), timeout=90)
    assert code != 0
    reservations = list(travel.AIRLINE.reservations.values())
    assert reservations
    assert reservations[0].status == "pending_confirmation"
    assert reservations[0].pnr is None


def test_travel_happy_path_verified(runtime_url: str) -> None:
    asyncio.run(_travel_ok(runtime_url))


async def _travel_ok(url: str) -> None:
    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    travel = _load("travel_booking_ok", ROOT / "examples" / "travel-booking" / "main.py")
    code = await asyncio.wait_for(travel.run_once("none"), timeout=90)
    if code != 0:
        async with httpx.AsyncClient(timeout=15) as client:
            runs = await client.get(f"{url}/api/v1/runs", params={"limit": 5})
            print("runs", runs.text[:2000])
            items = (runs.json().get("items") or runs.json()) if runs.status_code == 200 else []
            if isinstance(items, list) and items:
                rid = items[0].get("id") or items[0].get("run_id")
                ev = await client.get(f"{url}/api/v1/runs/{rid}/events", params={"limit": 50})
                print("events", ev.text[:4000])
    assert code == 0
    reservations = list(travel.AIRLINE.reservations.values())
    assert len(reservations) == 1
    assert reservations[0].status == "confirmed"
    assert reservations[0].pnr


def test_enterprise_revoke_prevents_provision(runtime_url: str) -> None:
    asyncio.run(_access_revoke(runtime_url))


async def _access_revoke(url: str) -> None:
    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    access = _load("enterprise_access_main", ROOT / "examples" / "enterprise-access" / "main.py")
    task = asyncio.create_task(access.run_once("none"))
    await asyncio.sleep(0.8)
    access.IDP.revoke_eligibility("USER-ada")
    try:
        await _approve_named(url, "access_agent", timeout=20)
    except TimeoutError:
        pass
    code = await asyncio.wait_for(task, timeout=90)
    assert "payments.admin" not in access.IDP.users["USER-ada"].roles
    assert code != 0
