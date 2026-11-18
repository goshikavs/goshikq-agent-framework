"""In-memory core-banking store for the bank-account-update example.

An update acknowledgement is not the same as an applied, versioned account row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Fault(str, Enum):
    NONE = "none"
    VERSION_CONFLICT = "version_conflict"
    REJECTED_AUTH = "rejected_auth"
    READBACK_MISMATCH = "readback_mismatch"


@dataclass
class Account:
    id: str
    holder: str
    routing: str
    last4: str
    version: int
    core_status: str = "active"
    pending_routing: str | None = None


@dataclass
class SimulatedBank:
    fault: str = Fault.NONE
    accounts: dict[str, Account] = field(default_factory=dict)
    apply_count: int = 0
    last_ack: dict | None = None

    def lookup(self, account_id: str) -> dict:
        a = self.accounts.get(account_id)
        if not a:
            return {"found": False, "account_id": account_id}
        return {
            "found": True,
            "account_id": a.id,
            "holder": a.holder,
            "routing": a.routing,
            "last4": a.last4,
            "version": a.version,
            "core_status": a.core_status,
        }

    def authorize(self, account_id: str, actor: str) -> dict:
        a = self.accounts.get(account_id)
        if not a:
            return {"authorized": False, "reason": "unknown_account"}
        if self.fault == Fault.REJECTED_AUTH or actor != a.holder:
            return {"authorized": False, "reason": "actor_mismatch", "version": a.version}
        return {"authorized": True, "account_id": account_id, "version": a.version}

    def apply_update(self, account_id: str, new_routing: str, expected_version: int) -> dict:
        a = self.accounts[account_id]
        self.apply_count += 1
        if a.version != expected_version:
            return {
                "accepted": False,
                "applied": False,
                "reason": "version_conflict",
                "version": a.version,
            }
        a.pending_routing = new_routing
        a.core_status = "update_pending"
        self.last_ack = {"accepted": True, "applied": False, "account_id": account_id, "version": a.version}
        if self.fault == Fault.READBACK_MISMATCH:
            # Acknowledgement claims success; authoritative row stays on the old routing.
            return dict(self.last_ack)
        a.routing = new_routing
        a.version += 1
        a.core_status = "applied"
        a.pending_routing = None
        self.last_ack = {
            "accepted": True,
            "applied": True,
            "account_id": account_id,
            "version": a.version,
            "routing": a.routing,
        }
        return dict(self.last_ack)

    def bump_version(self, account_id: str) -> None:
        self.accounts[account_id].version += 1

    def snapshot(self) -> dict:
        return {
            "accounts": {
                k: {
                    "id": v.id,
                    "holder": v.holder,
                    "routing": v.routing,
                    "last4": v.last4,
                    "version": v.version,
                    "core_status": v.core_status,
                    "pending_routing": v.pending_routing,
                }
                for k, v in self.accounts.items()
            }
        }


def demo_bank(fault: str = Fault.NONE) -> SimulatedBank:
    return SimulatedBank(
        fault=fault,
        accounts={
            "ACCT-1": Account(
                id="ACCT-1",
                holder="Ada",
                routing="021000021",
                last4="4242",
                version=3,
            )
        },
    )
