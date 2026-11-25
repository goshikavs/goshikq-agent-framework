"""A stale lease holder must not persist VERIFIED after another worker wins.

Server A pauses before the terminal row write. The test expires A's lease,
starts server B on the same PostgreSQL, and lets B finish the run. A then
resumes and must leave B's row unchanged.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from goshikq_ai import Agent, Goal, Runtime, StateSnapshot  # noqa: E402
from goshikq_ai.models import MockModel, ModelTurn  # noqa: E402
from tests.helpers import find_server  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _tcp_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _start(port: int, env: dict[str, str]) -> subprocess.Popen:
    binary = find_server()
    if binary is None:
        pytest.skip("goshikq-server binary not found")
    log_dir = ROOT / "target" / "test-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"lease-{port}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    kwargs: dict = {
        "env": env,
        "cwd": str(ROOT),
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([str(binary)], **kwargs)
    proc._log = str(log_path)  # type: ignore[attr-defined]
    return proc


def _wait_http(url: str, proc: subprocess.Popen, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            tail = Path(proc._log).read_text(encoding="utf-8", errors="replace")[-2000:]  # type: ignore[attr-defined]
            raise RuntimeError(f"server exited {proc.returncode}\n{tail}")
        try:
            if httpx.get(f"{url}/health", timeout=1).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    tail = Path(proc._log).read_text(encoding="utf-8", errors="replace")[-2000:]  # type: ignore[attr-defined]
    raise TimeoutError(f"server not ready at {url}\n{tail}")


def _psql(pg_dir: Path, pg_port: int, sql: str) -> str:
    names = ["psql.exe", "psql"] if os.name == "nt" else ["psql"]
    binary = None
    for name in names:
        found = list(pg_dir.rglob(name))
        if found:
            binary = found[0]
            break
    if binary is None:
        pytest.skip("psql not found in embedded install")
    env = os.environ.copy()
    env["PGPASSWORD"] = "goshikq"
    proc = subprocess.run(
        [str(binary), "-h", "127.0.0.1", "-p", str(pg_port), "-U", "postgres", "-d", "goshikq", "-At", "-c", sql],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _row(pg_dir: Path, pg_port: int, run_id: str) -> dict[str, str]:
    raw = _psql(
        pg_dir,
        pg_port,
        "SELECT status || '|' || verification_status || '|' || lease_generation::text || '|' || COALESCE(lease_owner,'') "
        f"FROM runs WHERE id = '{run_id}'",
    )
    status, verification, generation, owner = raw.split("|", 3)
    return {
        "status": status,
        "verification_status": verification,
        "lease_generation": generation,
        "lease_owner": owner,
    }


@pytest.mark.parametrize("winner_verifies", [True, False])
def test_stale_worker_cannot_overwrite_winner(winner_verifies: bool, tmp_path: Path) -> None:
    asyncio.run(_race(winner_verifies, tmp_path))


async def _race(winner_verifies: bool, tmp_path: Path) -> None:
    binary = find_server()
    if binary is None:
        pytest.skip("goshikq-server binary not found")
    http_a = _free_port()
    http_b = _free_port()
    pg_port = _free_port()
    pg_dir = ROOT / "target" / "test-pg" / f"lease-{pg_port}"
    shared = ROOT / "target" / "test-pg" / "shared" / "install"
    if shared.exists() and not (pg_dir / "install").exists():
        pg_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(shared, pg_dir / "install")
    pause_dir = tmp_path / "pause"
    pause_dir.mkdir()
    store = {"order": {"status": "refunded"}, "refund": {"status": "settled"}}
    agent_name = f"lease_agent_{uuid.uuid4().hex[:8]}"

    def success(state: StateSnapshot) -> bool:
        return state.get("refund.status") == "settled" and state.get("order.status") == "refunded"

    class Provider:
        def snapshot(self, context):  # noqa: ANN001
            return StateSnapshot(state={"order": dict(store["order"]), "refund": dict(store["refund"])}, version="1", source="lease")

        def version(self, resource_id: str) -> str:
            return "1"

    env_a = os.environ.copy()
    env_a.update(
        {
            "DATABASE_URL": "embedded",
            "GOSHIKQ_BIND": f"127.0.0.1:{http_a}",
            "GOSHIKQ_AUTH_MODE": "none",
            "GOSHIKQ_EMBEDDED_PG_PORT": str(pg_port),
            "GOSHIKQ_EMBEDDED_PG_DIR": str(pg_dir),
            "GOSHIKQ_LEASE_TTL_SECS": "30",
            "GOSHIKQ_PAUSE_AT": "before_terminal_write",
            "GOSHIKQ_PAUSE_DIR": str(pause_dir),
            "RUST_LOG": "warn",
        }
    )
    url_a = f"http://127.0.0.1:{http_a}"
    proc_a = _start(http_a, env_a)
    proc_b: subprocess.Popen | None = None
    try:
        await asyncio.to_thread(_wait_http, url_a, proc_a)
        goal = Goal(description="settled refund", success=success, max_steps=4)
        agent = Agent(
            name=agent_name,
            model=MockModel(script=[ModelTurn(content="The refund is verified.")]),
            tools=[],
        )

        async def run_a():
            async with Runtime(agent, endpoint=url_a, state_provider=Provider(), poll_timeout_ms=2_000) as rt:
                return await rt.run(goal, input={})

        task = asyncio.create_task(run_a())
        run_id = None
        deadline = time.monotonic() + 60
        async with httpx.AsyncClient(timeout=5) as client:
            while time.monotonic() < deadline and run_id is None:
                listed = await client.get(f"{url_a}/api/v1/runs", params={"limit": 20})
                items = listed.json().get("items") or [] if listed.status_code == 200 else []
                mine = [i for i in items if i.get("agent_name") == agent_name]
                if mine:
                    run_id = mine[0]["id"]
                await asyncio.sleep(0.1)
        assert run_id, "run was not created"
        paused = pause_dir / f"paused-{run_id}"
        while time.monotonic() < deadline and not paused.exists():
            await asyncio.sleep(0.05)
        assert paused.exists(), "executor did not pause before the terminal write"
        before = _row(pg_dir, pg_port, run_id)
        assert before["verification_status"] != "VERIFIED"
        _psql(
            pg_dir,
            pg_port,
            f"UPDATE runs SET lease_expires_at = now() - interval '5 seconds' WHERE id = '{run_id}'",
        )
        if not winner_verifies:
            store["order"]["status"] = "paid"
            store["refund"]["status"] = "reversed"
        env_b = os.environ.copy()
        env_b.update(
            {
                "DATABASE_URL": f"postgres://postgres:goshikq@127.0.0.1:{pg_port}/goshikq",
                "GOSHIKQ_BIND": f"127.0.0.1:{http_b}",
                "GOSHIKQ_AUTH_MODE": "none",
                "GOSHIKQ_LEASE_TTL_SECS": "30",
                "RUST_LOG": "warn",
            }
        )
        url_b = f"http://127.0.0.1:{http_b}"
        proc_b = _start(http_b, env_b)
        await asyncio.to_thread(_wait_http, url_b, proc_b)
        agent_b = Agent(
            name=agent_name,
            model=MockModel(script=[ModelTurn(content="worker B observed the ledger.")]),
            tools=[],
        )
        async with Runtime(agent_b, endpoint=url_b, state_provider=Provider()) as rt_b:
            await asyncio.wait_for(rt_b.attach(run_id, goal), timeout=90)
        (pause_dir / f"release-{run_id}").write_text("1", encoding="utf-8")
        try:
            await asyncio.wait_for(task, timeout=60)
        except TimeoutError:
            tail_a = Path(proc_a._log).read_text(encoding="utf-8", errors="replace")[-1500:]  # type: ignore[attr-defined]
            tail_b = Path(proc_b._log).read_text(encoding="utf-8", errors="replace")[-1500:] if proc_b else ""  # type: ignore[attr-defined]
            row = _row(pg_dir, pg_port, run_id)
            raise AssertionError(f"worker A did not finish\nrow={row}\nA={tail_a}\nB={tail_b}")
        after = _row(pg_dir, pg_port, run_id)
        assert int(after["lease_generation"]) > int(before["lease_generation"])
        assert after["lease_owner"] != before["lease_owner"]
        assert after["status"] in {"COMPLETED", "UNVERIFIED", "FAILED"}
        if winner_verifies:
            assert after["status"] == "COMPLETED"
            assert after["verification_status"] == "VERIFIED"
        else:
            assert after["verification_status"] != "VERIFIED"
        async with httpx.AsyncClient(timeout=10) as client:
            body = (await client.get(f"{url_b}/api/v1/runs/{run_id}")).json()
        assert body["status"] == after["status"]
        assert body["verification_status"] == after["verification_status"]
        if proc_a.poll() is None:
            proc_a.kill()
            proc_a.wait(timeout=15)
        if proc_b.poll() is None:
            proc_b.kill()
            proc_b.wait(timeout=15)
        proc_b = None
        # Postgres on Windows often keeps listening. Replay must not rewrite the row.
        deadline = time.monotonic() + 20
        while _tcp_open(pg_port) and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
        env_c = dict(env_b)
        env_c["GOSHIKQ_BIND"] = f"127.0.0.1:{_free_port()}"
        if not _tcp_open(pg_port):
            pytest.skip("embedded postgres exited with the servers; restart replay not observable")
        proc_c = _start(int(env_c["GOSHIKQ_BIND"].rsplit(":", 1)[1]), env_c)
        try:
            url_c = f"http://{env_c['GOSHIKQ_BIND']}"
            await asyncio.to_thread(_wait_http, url_c, proc_c)
            async with httpx.AsyncClient(timeout=10) as client:
                replay = (await client.get(f"{url_c}/api/v1/runs/{run_id}")).json()
            assert replay["status"] == after["status"]
            assert replay["verification_status"] == after["verification_status"]
            replay_row = _row(pg_dir, pg_port, run_id)
            assert replay_row["verification_status"] == after["verification_status"]
            assert replay_row["status"] == after["status"]
        finally:
            if proc_c.poll() is None:
                proc_c.kill()
    finally:
        for proc in (proc_a, proc_b):
            if proc is not None and proc.poll() is None:
                proc.kill()
