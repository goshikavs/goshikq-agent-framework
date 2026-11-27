"""External execution lifecycle. Wire values match `goshikq_protocol::ExternalLifecycle`."""

from __future__ import annotations

from enum import StrEnum


class ExternalLifecycle(StrEnum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    DISPATCH_IN_PROGRESS = "DISPATCH_IN_PROGRESS"
    DISPATCH_OUTCOME_UNKNOWN = "DISPATCH_OUTCOME_UNKNOWN"
    EXTERNAL_RUNNING = "EXTERNAL_RUNNING"
    EXTERNAL_SUSPENDED = "EXTERNAL_SUSPENDED"
    EXTERNAL_COMPLETED = "EXTERNAL_COMPLETED"
    EXTERNAL_FAILED = "EXTERNAL_FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_INCONCLUSIVE = "VERIFICATION_INCONCLUSIVE"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in {
            ExternalLifecycle.VERIFIED,
            ExternalLifecycle.VERIFICATION_FAILED,
            ExternalLifecycle.VERIFICATION_INCONCLUSIVE,
            ExternalLifecycle.CANCELLED,
        }


_EDGES: set[tuple[ExternalLifecycle, ExternalLifecycle]] = {
    (ExternalLifecycle.NOT_DISPATCHED, ExternalLifecycle.DISPATCH_IN_PROGRESS),
    (ExternalLifecycle.DISPATCH_IN_PROGRESS, ExternalLifecycle.EXTERNAL_RUNNING),
    (ExternalLifecycle.DISPATCH_IN_PROGRESS, ExternalLifecycle.EXTERNAL_SUSPENDED),
    (ExternalLifecycle.DISPATCH_IN_PROGRESS, ExternalLifecycle.EXTERNAL_COMPLETED),
    (ExternalLifecycle.DISPATCH_IN_PROGRESS, ExternalLifecycle.EXTERNAL_FAILED),
    (ExternalLifecycle.DISPATCH_IN_PROGRESS, ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN),
    (ExternalLifecycle.DISPATCH_IN_PROGRESS, ExternalLifecycle.RECONCILIATION_REQUIRED),
    (ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN, ExternalLifecycle.RECONCILIATION_REQUIRED),
    (ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN, ExternalLifecycle.EXTERNAL_RUNNING),
    (ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN, ExternalLifecycle.EXTERNAL_SUSPENDED),
    (ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN, ExternalLifecycle.EXTERNAL_COMPLETED),
    (ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN, ExternalLifecycle.EXTERNAL_FAILED),
    (ExternalLifecycle.EXTERNAL_RUNNING, ExternalLifecycle.EXTERNAL_SUSPENDED),
    (ExternalLifecycle.EXTERNAL_RUNNING, ExternalLifecycle.EXTERNAL_COMPLETED),
    (ExternalLifecycle.EXTERNAL_RUNNING, ExternalLifecycle.EXTERNAL_FAILED),
    (ExternalLifecycle.EXTERNAL_RUNNING, ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN),
    (ExternalLifecycle.EXTERNAL_RUNNING, ExternalLifecycle.RECONCILIATION_REQUIRED),
    (ExternalLifecycle.EXTERNAL_RUNNING, ExternalLifecycle.CANCEL_REQUESTED),
    (ExternalLifecycle.EXTERNAL_SUSPENDED, ExternalLifecycle.EXTERNAL_RUNNING),
    (ExternalLifecycle.EXTERNAL_SUSPENDED, ExternalLifecycle.EXTERNAL_COMPLETED),
    (ExternalLifecycle.EXTERNAL_SUSPENDED, ExternalLifecycle.EXTERNAL_FAILED),
    (ExternalLifecycle.EXTERNAL_SUSPENDED, ExternalLifecycle.RECONCILIATION_REQUIRED),
    (ExternalLifecycle.EXTERNAL_SUSPENDED, ExternalLifecycle.CANCEL_REQUESTED),
    (ExternalLifecycle.EXTERNAL_COMPLETED, ExternalLifecycle.AWAITING_VERIFICATION),
    (ExternalLifecycle.EXTERNAL_FAILED, ExternalLifecycle.RECONCILIATION_REQUIRED),
    (ExternalLifecycle.RECONCILIATION_REQUIRED, ExternalLifecycle.EXTERNAL_RUNNING),
    (ExternalLifecycle.RECONCILIATION_REQUIRED, ExternalLifecycle.EXTERNAL_SUSPENDED),
    (ExternalLifecycle.RECONCILIATION_REQUIRED, ExternalLifecycle.EXTERNAL_COMPLETED),
    (ExternalLifecycle.RECONCILIATION_REQUIRED, ExternalLifecycle.EXTERNAL_FAILED),
    (ExternalLifecycle.RECONCILIATION_REQUIRED, ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN),
    (ExternalLifecycle.RECONCILIATION_REQUIRED, ExternalLifecycle.AWAITING_VERIFICATION),
    (ExternalLifecycle.CANCEL_REQUESTED, ExternalLifecycle.CANCELLED),
    (ExternalLifecycle.CANCEL_REQUESTED, ExternalLifecycle.RECONCILIATION_REQUIRED),
    (ExternalLifecycle.CANCEL_REQUESTED, ExternalLifecycle.EXTERNAL_RUNNING),
    (ExternalLifecycle.CANCEL_REQUESTED, ExternalLifecycle.EXTERNAL_FAILED),
}

_VERIFICATION = {
    ExternalLifecycle.VERIFIED,
    ExternalLifecycle.VERIFICATION_FAILED,
    ExternalLifecycle.VERIFICATION_INCONCLUSIVE,
}


def allow_transition(current: ExternalLifecycle, nxt: ExternalLifecycle) -> bool:
    if current == nxt:
        return True
    if nxt in _VERIFICATION:
        return False
    return (current, nxt) in _EDGES


def verify_outcome(
    current: ExternalLifecycle,
    *,
    predicate_passed: bool,
    evidence_source: str,
    framework: str,
) -> ExternalLifecycle:
    if current != ExternalLifecycle.AWAITING_VERIFICATION:
        raise ValueError("verification requires AWAITING_VERIFICATION")
    if not evidence_source.strip():
        raise ValueError("verification requires an evidence source")
    if evidence_source.lower() == framework.lower():
        raise ValueError("framework claims are not authoritative evidence")
    if predicate_passed:
        return ExternalLifecycle.VERIFIED
    return ExternalLifecycle.VERIFICATION_INCONCLUSIVE
