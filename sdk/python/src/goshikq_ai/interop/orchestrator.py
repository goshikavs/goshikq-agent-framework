"""Coordinate one external framework execution without treating its result as verified."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contract import ExternalObservation, FrameworkAdapter, UnsupportedCapability
from .ledger import ExecutionRecord, SqliteLedger, new_id
from .lifecycle import ExternalLifecycle, allow_transition, verify_outcome

_KIND_TO_LIFECYCLE = {
    "unknown": ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN,
    "running": ExternalLifecycle.EXTERNAL_RUNNING,
    "suspended": ExternalLifecycle.EXTERNAL_SUSPENDED,
    "completed": ExternalLifecycle.EXTERNAL_COMPLETED,
    "failed": ExternalLifecycle.EXTERNAL_FAILED,
    "cancel_confirmed": ExternalLifecycle.CANCELLED,
}


@dataclass
class OrchestratorResult:
    record: ExecutionRecord
    reused: bool = False


class ExternalOrchestrator:
    def __init__(self, adapter: FrameworkAdapter, ledger: SqliteLedger, *, project_id: str) -> None:
        self.adapter = adapter
        self.ledger = ledger
        self.project_id = project_id

    def start(
        self,
        *,
        run_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        correlation_id: str,
        tenant_id: str | None = None,
        parent_run_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
    ) -> OrchestratorResult:
        existing = self.ledger.get_by_idempotency(self.project_id, idempotency_key)
        if existing is not None:
            existing.reused = True
            return OrchestratorResult(record=existing, reused=True)
        caps = self.adapter.describe_capabilities()
        record = ExecutionRecord(
            id=new_id(),
            project_id=self.project_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
            task_id=task_id,
            tenant_id=tenant_id,
            framework=self.adapter.framework,
            adapter_version=self.adapter.adapter_version,
            framework_version=self.adapter.framework_version,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            trace_id=trace_id,
            dispatch_id=new_id(),
            lifecycle=ExternalLifecycle.NOT_DISPATCHED,
            capabilities=caps.to_dict(),
            evidence={},
        )
        record = self.ledger.insert(record)
        thread_id = record.id
        self._move(record, ExternalLifecycle.DISPATCH_IN_PROGRESS)
        record.external_thread_id = thread_id
        self.ledger.save(record)
        try:
            observation = self.adapter.start(
                thread_id=thread_id,
                payload=payload,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            record.error = str(exc)
            self._move(record, ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN)
            self.ledger.save(record)
            raise
        self._apply_observation(record, observation)
        return OrchestratorResult(record=self.ledger.save(record))

    def resume(self, execution_id: str, value: Any) -> ExecutionRecord:
        self.adapter.describe_capabilities().require(self.adapter.framework, "native_suspend_resume")
        record = self._load(execution_id)
        if record.lifecycle != ExternalLifecycle.EXTERNAL_SUSPENDED:
            raise ValueError("resume requires EXTERNAL_SUSPENDED")
        if not record.external_thread_id:
            raise ValueError("resume requires an external thread id")
        observation = self.adapter.resume(thread_id=record.external_thread_id, value=value)
        self._apply_observation(record, observation)
        return self.ledger.save(record)

    def reconcile(self, execution_id: str) -> ExecutionRecord:
        record = self._load(execution_id)
        if record.lifecycle.terminal:
            return record
        if not record.external_thread_id:
            self._move(record, ExternalLifecycle.RECONCILIATION_REQUIRED)
            return self.ledger.save(record)
        self.adapter.describe_capabilities().require(self.adapter.framework, "external_run_status")
        observation = self.adapter.get_status(thread_id=record.external_thread_id)
        if observation.kind == "unknown":
            target = ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN
            if not allow_transition(record.lifecycle, target):
                target = ExternalLifecycle.RECONCILIATION_REQUIRED
            self._move(record, target)
            record.error = observation.error or "external state is unknown"
            return self.ledger.save(record)
        self._apply_observation(record, observation)
        return self.ledger.save(record)

    def cancel(self, execution_id: str) -> ExecutionRecord:
        record = self._load(execution_id)
        caps = self.adapter.describe_capabilities()
        if not caps.native_cancellation:
            raise UnsupportedCapability(self.adapter.framework, "native_cancellation")
        if not record.external_thread_id:
            raise ValueError("cancel requires an external thread id")
        self._move(record, ExternalLifecycle.CANCEL_REQUESTED)
        observation = self.adapter.cancel(thread_id=record.external_thread_id)
        if observation.kind != "cancel_confirmed":
            self._move(record, ExternalLifecycle.RECONCILIATION_REQUIRED)
            record.error = "cancellation was not confirmed"
            return self.ledger.save(record)
        self._move(record, ExternalLifecycle.CANCELLED)
        return self.ledger.save(record)

    def accept_for_verification(self, execution_id: str) -> ExecutionRecord:
        record = self._load(execution_id)
        self._move(record, ExternalLifecycle.AWAITING_VERIFICATION)
        return self.ledger.save(record)

    def verify(
        self,
        execution_id: str,
        *,
        predicate_passed: bool,
        evidence_source: str,
        evidence_fingerprint: str,
    ) -> ExecutionRecord:
        record = self._load(execution_id)
        nxt = verify_outcome(
            record.lifecycle,
            predicate_passed=predicate_passed,
            evidence_source=evidence_source,
            framework=record.framework,
        )
        record.lifecycle = nxt
        evidence = dict(record.evidence or {})
        evidence["verification"] = {
            "predicate_passed": predicate_passed,
            "evidence_source": evidence_source,
            "evidence_fingerprint": evidence_fingerprint,
            "framework_claim_accepted": False,
        }
        record.evidence = evidence
        return self.ledger.save(record)

    def _load(self, execution_id: str) -> ExecutionRecord:
        record = self.ledger.get(self.project_id, execution_id)
        if record is None:
            raise KeyError(execution_id)
        return record

    def _move(self, record: ExecutionRecord, nxt: ExternalLifecycle) -> None:
        if not allow_transition(record.lifecycle, nxt):
            raise ValueError(f"cannot move {record.lifecycle} to {nxt}")
        record.lifecycle = nxt

    def _apply_observation(self, record: ExecutionRecord, observation: ExternalObservation) -> None:
        nxt = _KIND_TO_LIFECYCLE[observation.kind]
        if nxt == ExternalLifecycle.CANCELLED and record.lifecycle != ExternalLifecycle.CANCEL_REQUESTED:
            raise ValueError("confirmed cancellation requires CANCEL_REQUESTED")
        self._move(record, nxt)
        if observation.external_run_id:
            record.external_run_id = observation.external_run_id
        if observation.external_thread_id:
            record.external_thread_id = observation.external_thread_id
        if observation.payload:
            record.result = observation.payload
        if observation.error:
            record.error = observation.error
        if observation.usage:
            evidence = dict(record.evidence or {})
            evidence["usage"] = observation.usage
            record.evidence = evidence
