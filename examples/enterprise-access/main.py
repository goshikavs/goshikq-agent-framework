"""Enterprise access provisioning: an IdP ticket is not membership.

Usage:
    python main.py
    python main.py --fault idp_reject
    python main.py --fault revoke_after_approval
    python main.py --fault unauthorized
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

from access_world import Fault, SimulatedIdp, demo_idp

IDP: SimulatedIdp = demo_idp()
ROLE = "payments.admin"


def _verify_membership(arguments: dict, output, state: StateSnapshot):
    user_id = arguments.get("user_id")
    user = (state.get("users") or {}).get(user_id or "")
    if not user:
        return VerifierResult.inconclusive("user missing from snapshot")
    roles = user.get("roles") or []
    actual = {"roles": roles, "eligible": user.get("eligible")}
    if ROLE in roles and user.get("eligible"):
        return VerifierResult.verified(expected={"role": ROLE}, actual=actual, method="idp.membership")
    if output and isinstance(output, dict) and output.get("accepted") and ROLE not in roles:
        return VerifierResult.waiting(
            "IdP accepted the ticket but membership is not visible",
            expected={"role": ROLE},
            actual=actual,
            method="idp.membership",
        )
    return VerifierResult.inconclusive(f"roles={roles}", method="idp.membership")


@tool(effect="read_only")
def check_permissions(user_id: str) -> dict:
    raw = IDP.permissions(user_id)
    user = IDP.users.get(user_id)
    return with_evidence(
        raw,
        [
            Evidence(
                source_system="idp",
                resource_id=f"user:{user_id}",
                resource_version=str(user.version) if user else None,
                trust="authoritative",
                access_scope="iam-read",
            )
        ],
        DecisionRef(
            id=f"dec:perm:{user_id}",
            kind="authorization",
            depends_on=[f"user:{user_id}"],
            action="act:provision_role",
            payload={"resource_id": f"user:{user_id}", "role": ROLE},
        ),
    )


@tool(
    effect="non_idempotent_write",
    risk="critical",
    requires_approval=True,
    permissions=["iam:provision"],
    verifier=_verify_membership,
    required_evidence=["user:{user_id}"],
    required_invariants=["authorization"],
    on_missing_evidence="block",
    revalidation_policy="strict_contract",
)
def provision_role(user_id: str, role: str) -> dict:
    return IDP.provision(user_id, role)


class IdpProvider:
    def snapshot(self, context: SnapshotContext) -> StateSnapshot:
        return StateSnapshot(state=IDP.snapshot(), version=str(IDP.users["USER-ada"].version), source="idp")

    def version(self, resource_id: str) -> str | None:
        key = resource_id.removeprefix("user:")
        user = IDP.users.get(key)
        return str(user.version) if user else None


def has_role(state: StateSnapshot) -> InvariantOutcome:
    user = (state.get("users") or {}).get("USER-ada") or {}
    ok = ROLE in (user.get("roles") or []) and user.get("eligible") is True
    return InvariantOutcome(ok, expected={"role": ROLE}, actual=user.get("roles"), reason=None if ok else "membership missing")


def policy(messages, tools, idx: int) -> ModelTurn:
    if idx == 0:
        return ModelTurn(tool_calls=[("check_permissions", {"user_id": "USER-ada"})])
    perm = last_tool_result(messages, "check_permissions") or {}
    inner = perm.get("result", perm)
    if not inner.get("allowed"):
        return ModelTurn(content=f"Not eligible: {inner.get('reason')}")
    if idx == 1:
        return ModelTurn(tool_calls=[("provision_role", {"user_id": "USER-ada", "role": ROLE})])
    return ModelTurn(content="Provisioning requested.")


async def run_once(fault: str) -> int:
    global IDP
    IDP = demo_idp(fault)
    agent = Agent(
        name="access_agent",
        model=MockModel(policy=policy),
        tools=[check_permissions, provision_role],
        permissions=["iam:provision"],
    )
    goal = Goal(description="USER-ada is a payments.admin in the IdP", success=has_role, max_steps=6)
    async with Runtime(agent, state_provider=IdpProvider()) as rt:
        result = await rt.run(goal, input={"user_id": "USER-ada", "fault": fault})
    print(result.summary())
    print(f"roles: {IDP.users['USER-ada'].roles}")
    print(f"eligible: {IDP.users['USER-ada'].eligible}")
    print(f"provision_count: {IDP.provision_count}")
    return 0 if result.verified else 1


def main() -> int:
    logging.basicConfig(level=os.environ.get("GOSHIKQ_LOG", "WARNING"))
    p = argparse.ArgumentParser(description="Goshikq enterprise access demo")
    p.add_argument("--fault", default=Fault.NONE, choices=[e.value for e in Fault])
    args = p.parse_args()
    return asyncio.run(run_once(args.fault))


if __name__ == "__main__":
    sys.exit(main())
