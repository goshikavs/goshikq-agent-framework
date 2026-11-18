"""A model claiming success is not a verified business outcome.

Requires goshikq-server (see tests/helpers.find_server) and DATABASE_URL.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

# runtime_url: session fixture in conftest.py

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from goshikq_ai import Agent, Goal, Runtime, StateSnapshot, tool  # noqa: E402
from goshikq_ai.models import MockModel, ModelTurn  # noqa: E402
from goshikq_ai.state import SnapshotContext  # noqa: E402


def test_lying_model_text_is_not_verified(runtime_url: str) -> None:
    asyncio.run(_lying_model(runtime_url))


async def _lying_model(url: str) -> None:
    store = {"order": {"status": "paid"}, "refund": {"status": "none"}}

    @tool(effect="read_only")
    def lookup() -> dict:
        return dict(store)

    class Provider:
        def snapshot(self, context: SnapshotContext) -> StateSnapshot:
            return StateSnapshot(state=dict(store), version="1", source="mem")

        def version(self, resource_id: str) -> str | None:
            return "1"

    def settled(state: StateSnapshot) -> bool:
        return state.get("order.status") == "refunded" and state.get("refund.status") == "settled"

    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    agent = Agent(
        name="liar_agent",
        model=MockModel(script=[ModelTurn(content="Refund settled successfully.")]),
        tools=[lookup],
    )
    goal = Goal(description="order refunded and settled", success=settled, max_steps=4)
    async with Runtime(agent, endpoint=url, state_provider=Provider()) as rt:
        result = await rt.run(goal, input={"order_id": "ORD-1"})
    assert result.verified is False
    assert str(result.verification_status).upper() != "VERIFIED"
    assert store["refund"]["status"] != "settled"


def test_tool_ack_without_settlement_is_not_verified(runtime_url: str) -> None:
    asyncio.run(_ack_is_not_settled(runtime_url))


async def _ack_is_not_settled(url: str) -> None:
    store = {"order": {"status": "paid"}, "refund": {"status": "none"}}

    @tool(effect="idempotent_write", idempotent=True, risk="high")
    def submit() -> dict:
        store["refund"]["status"] = "accepted"
        store["order"]["status"] = "refund_pending"
        return {"accepted": True, "settled": False}

    class Provider:
        def snapshot(self, context: SnapshotContext) -> StateSnapshot:
            return StateSnapshot(state={"orders": {"x": dict(store["order"])}, "refunds": {"r": dict(store["refund"])}}, version="1", source="mem")

        def version(self, resource_id: str) -> str | None:
            return "1"

    def settled(state: StateSnapshot) -> bool:
        order = (state.get("orders") or {}).get("x") or {}
        refund = (state.get("refunds") or {}).get("r") or {}
        return order.get("status") == "refunded" and refund.get("status") == "settled"

    os.environ["GOSHIKQ_RUNTIME_URL"] = url
    agent = Agent(
        name="ack_agent",
        model=MockModel(
            script=[
                ModelTurn(tool_calls=[("submit", {})]),
                ModelTurn(content="Processor accepted. Done."),
            ]
        ),
        tools=[submit],
        permissions=[],
    )
    goal = Goal(description="settled refund", success=settled, max_steps=6, external_wait_seconds=3)
    async with Runtime(agent, endpoint=url, state_provider=Provider()) as rt:
        result = await rt.run(goal, input={})
    assert result.verified is False
    assert store["refund"]["status"] == "accepted"
