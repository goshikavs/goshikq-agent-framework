"""Bank account routing update: acknowledgement is not an applied core-banking row.

Usage:
    python main.py
    python main.py --fault version_conflict
    python main.py --fault rejected_auth
    python main.py --fault readback_mismatch
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from goshikq_ai import Agent, DecisionRef, Evidence, Goal, InvariantOutcome, Runtime, StateSnapshot, tool, with_evidence
from goshikq_ai.models import MockModel, ModelTurn, last_tool_result
from goshikq_ai.state import SnapshotContext
from goshikq_ai.tools import VerifierResult

from bank_world import Fault, SimulatedBank, demo_bank

BANK: SimulatedBank = demo_bank()
NEW_ROUTING = "026009593"


def _verify_applied(arguments: dict, output, state: StateSnapshot):
    account_id = arguments.get("account_id")
    acct = (state.get("accounts") or {}).get(account_id or "")
    if not acct:
        return VerifierResult.inconclusive("account missing from snapshot")
    actual = {"routing": acct.get("routing"), "core_status": acct.get("core_status"), "version": acct.get("version")}
    if acct.get("routing") == NEW_ROUTING and acct.get("core_status") == "applied":
        return VerifierResult.verified(expected={"routing": NEW_ROUTING, "core_status": "applied"}, actual=actual, method="account.routing+core_status")
    if output and isinstance(output, dict) and output.get("accepted") and acct.get("core_status") != "applied":
        return VerifierResult.waiting(
            "core accepted the request but the authoritative row is not applied",
            expected={"routing": NEW_ROUTING, "core_status": "applied"},
            actual=actual,
            method="account.routing+core_status",
        )
    return VerifierResult.inconclusive(f"core_status={acct.get('core_status')}", method="account.core_status")


@tool(effect="read_only")
def lookup_account(account_id: str) -> dict:
    return BANK.lookup(account_id)


@tool(effect="read_only")
def check_authorization(account_id: str, actor: str) -> dict:
    raw = BANK.authorize(account_id, actor)
    acct = BANK.accounts.get(account_id)
    version = str(acct.version) if acct else None
    return with_evidence(
        raw,
        [
            Evidence(
                source_system="core-banking",
                resource_id=f"account:{account_id}",
                resource_version=version,
                trust="authoritative",
                access_scope="accounts-write",
            )
        ],
        DecisionRef(
            id=f"dec:auth:{account_id}",
            kind="authorization",
            depends_on=[f"account:{account_id}"],
            action="act:apply_account_update",
            payload={"resource_id": f"account:{account_id}"},
        ),
    )


@tool(
    effect="non_idempotent_write",
    risk="high",
    requires_approval=True,
    permissions=["accounts:update"],
    verifier=_verify_applied,
    required_evidence=["account:{account_id}"],
    required_invariants=["authorization"],
    on_missing_evidence="block",
    revalidation_policy="strict_contract",
)
def apply_account_update(account_id: str, new_routing: str, expected_version: int) -> dict:
    return BANK.apply_update(account_id, new_routing, expected_version)


class BankProvider:
    def snapshot(self, context: SnapshotContext) -> StateSnapshot:
        snap = BANK.snapshot()
        return StateSnapshot(state=snap, version=str(BANK.accounts["ACCT-1"].version), source="core-banking")

    def version(self, resource_id: str) -> str | None:
        key = resource_id.removeprefix("account:")
        acct = BANK.accounts.get(key)
        return str(acct.version) if acct else None


def routing_applied(state: StateSnapshot) -> InvariantOutcome:
    acct = (state.get("accounts") or {}).get("ACCT-1") or {}
    ok = acct.get("routing") == NEW_ROUTING and acct.get("core_status") == "applied"
    return InvariantOutcome(
        ok,
        expected={"routing": NEW_ROUTING, "core_status": "applied"},
        actual={"routing": acct.get("routing"), "core_status": acct.get("core_status")},
        reason=None if ok else "authoritative account row does not show applied routing",
    )


def single_apply(state: StateSnapshot) -> InvariantOutcome:
    return InvariantOutcome(BANK.apply_count <= 1, expected={"max_applies": 1}, actual=BANK.apply_count)


def policy(messages, tools, idx: int) -> ModelTurn:
    if idx == 0:
        return ModelTurn(tool_calls=[("lookup_account", {"account_id": "ACCT-1"})])
    if idx == 1:
        return ModelTurn(tool_calls=[("check_authorization", {"account_id": "ACCT-1", "actor": "Ada"})])
    auth = last_tool_result(messages, "check_authorization") or {}
    inner = auth.get("result", auth)
    if not inner.get("authorized"):
        return ModelTurn(content=f"Not authorized: {inner.get('reason')}")
    if idx == 2:
        return ModelTurn(
            tool_calls=[
                (
                    "apply_account_update",
                    {"account_id": "ACCT-1", "new_routing": NEW_ROUTING, "expected_version": int(inner.get("version") or 3)},
                )
            ]
        )
    return ModelTurn(content="Core banking accepted the routing update.")


async def run_once(fault: str) -> int:
    global BANK
    BANK = demo_bank(fault)
    os.environ["GOSHIKQ_BANK_FAULT"] = fault
    agent = Agent(
        name="bank_agent",
        model=MockModel(policy=policy),
        tools=[lookup_account, check_authorization, apply_account_update],
        permissions=["accounts:update"],
    )
    goal = Goal(description="ACCT-1 routing applied in core banking", success=routing_applied, invariants=[single_apply], max_steps=8)
    async with Runtime(agent, state_provider=BankProvider()) as rt:
        result = await rt.run(goal, input={"account_id": "ACCT-1", "fault": fault})
    print(result.summary())
    acct = BANK.accounts["ACCT-1"]
    print(f"core_status: {acct.core_status}")
    print(f"routing: {acct.routing}")
    print(f"version: {acct.version}")
    print(f"apply_count: {BANK.apply_count}")
    return 0 if result.verified else 1


def main() -> int:
    logging.basicConfig(level=os.environ.get("GOSHIKQ_LOG", "WARNING"))
    p = argparse.ArgumentParser(description="Goshikq bank account update demo")
    p.add_argument("--fault", default=Fault.NONE, choices=[e.value for e in Fault])
    args = p.parse_args()
    return asyncio.run(run_once(args.fault))


if __name__ == "__main__":
    sys.exit(main())
