"""Python SDK and TypeScript SDK against one runtime. Not a parent/child pair.

Parent/child verification remains covered by tests/multi_agent. This test proves
both packaged languages can complete VERIFIED runs on the same goshikq-server.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# runtime_url: session fixture in conftest.py

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from goshikq_ai import Agent, Goal, Runtime, StateSnapshot, tool  # noqa: E402
from goshikq_ai.models import MockModel, ModelTurn  # noqa: E402
from goshikq_ai.state import SnapshotContext  # noqa: E402


def test_python_then_typescript_verified_on_same_runtime(runtime_url: str) -> None:
    asyncio.run(_python_verified(runtime_url))
    bun = shutil.which("bun") or shutil.which("bun.exe")
    if bun is None:
        pytest.skip("bun not on PATH")
    env = os.environ.copy()
    env["GOSHIKQ_RUNTIME_URL"] = runtime_url
    r = subprocess.run(
        [bun, "test", "tests/live.test.ts"],
        cwd=str(ROOT / "sdk" / "typescript"),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stdout + r.stderr


async def _python_verified(url: str) -> None:
    store = {"ok": False}

    @tool(effect="idempotent_write", idempotent=True)
    def mark() -> dict:
        store["ok"] = True
        return {"ok": True}

    class Provider:
        def snapshot(self, context: SnapshotContext) -> StateSnapshot:
            return StateSnapshot(state=dict(store), version="1", source="mem")

        def version(self, resource_id: str) -> str | None:
            return "1"

    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    agent = Agent(
        name="py_together",
        model=MockModel(script=[ModelTurn(tool_calls=[("mark", {})]), ModelTurn(content="done")]),
        tools=[mark],
    )
    goal = Goal(description="ok", success=lambda st: st.get("ok") is True, max_steps=4)
    async with Runtime(agent, endpoint=url, state_provider=Provider()) as rt:
        result = await rt.run(goal, input={})
    assert result.verified, result.summary()
