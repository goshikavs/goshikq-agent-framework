"""Simulated identity provider. A provisioning ticket is not membership."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Fault(str, Enum):
    NONE = "none"
    IDP_REJECT = "idp_reject"
    REVOKE_AFTER_APPROVAL = "revoke_after_approval"
    UNAUTHORIZED = "unauthorized"


@dataclass
class Identity:
    user_id: str
    roles: list[str]
    version: int
    eligible: bool = True


@dataclass
class SimulatedIdp:
    fault: str = Fault.NONE
    users: dict[str, Identity] = field(default_factory=dict)
    tickets: dict[str, dict] = field(default_factory=dict)
    provision_count: int = 0

    def permissions(self, user_id: str) -> dict:
        u = self.users.get(user_id)
        if not u:
            return {"allowed": False, "reason": "unknown_user"}
        if self.fault == Fault.UNAUTHORIZED or not u.eligible:
            return {"allowed": False, "reason": "not_eligible", "version": u.version}
        return {
            "allowed": True,
            "user_id": user_id,
            "roles": list(u.roles),
            "version": u.version,
            "eligible": u.eligible,
        }

    def provision(self, user_id: str, role: str) -> dict:
        u = self.users[user_id]
        self.provision_count += 1
        ticket = {"user_id": user_id, "role": role, "status": "submitted"}
        if self.fault == Fault.IDP_REJECT or not u.eligible:
            ticket["status"] = "rejected"
            self.tickets[user_id] = ticket
            return {"accepted": False, "applied": False, "ticket": ticket}
        if role not in u.roles:
            u.roles.append(role)
            u.version += 1
        ticket["status"] = "applied"
        self.tickets[user_id] = ticket
        return {"accepted": True, "applied": True, "ticket": ticket, "roles": list(u.roles)}

    def revoke_eligibility(self, user_id: str) -> None:
        self.users[user_id].eligible = False
        self.users[user_id].version += 1

    def snapshot(self) -> dict:
        return {
            "users": {
                k: {"user_id": v.user_id, "roles": list(v.roles), "version": v.version, "eligible": v.eligible}
                for k, v in self.users.items()
            },
            "tickets": dict(self.tickets),
        }


def demo_idp(fault: str = Fault.NONE) -> SimulatedIdp:
    return SimulatedIdp(
        fault=fault,
        users={"USER-ada": Identity(user_id="USER-ada", roles=["engineer"], version=2, eligible=True)},
    )
