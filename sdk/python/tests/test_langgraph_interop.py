"""Real LangGraph 1.2.x adapter tests. No cloud model."""

from __future__ import annotations

import sqlite3
from importlib.metadata import version
from typing import Any, TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from goshikq_ai.interop import (
    ExternalLifecycle,
    ExternalOrchestrator,
    LangGraphAdapter,
    UnsupportedCapability,
)
from goshikq_ai.interop.ledger import SqliteLedger


class Analysis(TypedDict, total=False):
    requirement: str
    analysis: str
    approved: bool


def _compile(path: str, *, with_interrupt: bool = False, fail: bool = False) -> tuple[Any, list[int]]:
    calls = [0]

    def analyze(state: Analysis) -> dict[str, Any]:
        calls[0] += 1
        if fail:
            raise RuntimeError("analysis failed")
        return {"analysis": state["requirement"].strip().upper()}

    def gate(state: Analysis) -> dict[str, Any]:
        approved = interrupt({"analysis": state.get("analysis")})
        return {"approved": bool(approved)}

    builder = StateGraph(Analysis)
    builder.add_node("analyze", analyze)
    builder.add_edge(START, "analyze")
    if with_interrupt:
        builder.add_node("gate", gate)
        builder.add_edge("analyze", "gate")
        builder.add_edge("gate", END)
    else:
        builder.add_edge("analyze", END)
    conn = sqlite3.connect(path, check_same_thread=False)
    graph = builder.compile(checkpointer=SqliteSaver(conn))
    return graph, calls


def test_installed_langgraph_is_the_tested_line() -> None:
    installed = version("langgraph")
    assert installed.startswith("1.2."), installed


def test_success_is_not_verified(tmp_path) -> None:
    graph, calls = _compile(str(tmp_path / "graph.sqlite"))
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    started = orch.start(
        run_id="run-1",
        payload={"requirement": "ship the fix"},
        idempotency_key="idem-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        trace_id="trace-1",
    )
    assert calls == [1]
    assert started.record.lifecycle == ExternalLifecycle.EXTERNAL_COMPLETED
    assert started.record.result["state"]["analysis"] == "SHIP THE FIX"
    with pytest.raises(ValueError, match="AWAITING_VERIFICATION"):
        orch.verify(
            started.record.id,
            predicate_passed=True,
            evidence_source="test-runner",
            evidence_fingerprint="abc",
        )
    waiting = orch.accept_for_verification(started.record.id)
    assert waiting.lifecycle == ExternalLifecycle.AWAITING_VERIFICATION
    with pytest.raises(ValueError, match="not authoritative"):
        orch.verify(
            started.record.id,
            predicate_passed=True,
            evidence_source="langgraph",
            evidence_fingerprint="framework-claim",
        )
    denied = orch.verify(
        started.record.id,
        predicate_passed=False,
        evidence_source="test-runner",
        evidence_fingerprint="tests-failed",
    )
    assert denied.lifecycle == ExternalLifecycle.VERIFICATION_INCONCLUSIVE


def test_independent_evidence_verifies(tmp_path) -> None:
    graph, _calls = _compile(str(tmp_path / "graph.sqlite"))
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    started = orch.start(
        run_id="run-1",
        payload={"requirement": "ship"},
        idempotency_key="idem-1",
        correlation_id="corr-1",
    )
    orch.accept_for_verification(started.record.id)
    verified = orch.verify(
        started.record.id,
        predicate_passed=True,
        evidence_source="test-runner",
        evidence_fingerprint="sha256:ok",
    )
    assert verified.lifecycle == ExternalLifecycle.VERIFIED
    assert verified.evidence["verification"]["framework_claim_accepted"] is False


def test_duplicate_dispatch_does_not_rerun(tmp_path) -> None:
    graph, calls = _compile(str(tmp_path / "graph.sqlite"))
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    kwargs = {
        "run_id": "run-1",
        "payload": {"requirement": "once"},
        "idempotency_key": "idem-1",
        "correlation_id": "corr-1",
    }
    first = orch.start(**kwargs)
    second = orch.start(**kwargs)
    assert calls == [1]
    assert second.reused is True
    assert second.record.id == first.record.id


def test_interrupt_resume_and_restart(tmp_path) -> None:
    graph_path = str(tmp_path / "graph.sqlite")
    ledger_path = str(tmp_path / "ledger.sqlite")
    graph, _calls = _compile(graph_path, with_interrupt=True)
    ledger = SqliteLedger(ledger_path)
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    started = orch.start(
        run_id="run-1",
        payload={"requirement": "needs approval"},
        idempotency_key="idem-1",
        correlation_id="corr-1",
    )
    assert started.record.lifecycle == ExternalLifecycle.EXTERNAL_SUSPENDED
    ledger.close()

    restarted_graph, _ignored = _compile(graph_path, with_interrupt=True)
    restarted = ExternalOrchestrator(
        LangGraphAdapter(restarted_graph),
        SqliteLedger(ledger_path),
        project_id="project-a",
    )
    reconciled = restarted.reconcile(started.record.id)
    assert reconciled.lifecycle == ExternalLifecycle.EXTERNAL_SUSPENDED
    resumed = restarted.resume(started.record.id, True)
    assert resumed.lifecycle == ExternalLifecycle.EXTERNAL_COMPLETED
    assert resumed.result["state"]["approved"] is True


def test_unknown_thread_is_not_success(tmp_path) -> None:
    graph, _calls = _compile(str(tmp_path / "graph.sqlite"))
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    started = orch.start(
        run_id="run-1",
        payload={"requirement": "present"},
        idempotency_key="idem-1",
        correlation_id="corr-1",
    )
    started.record.external_thread_id = "missing-thread"
    started.record.lifecycle = ExternalLifecycle.DISPATCH_IN_PROGRESS
    ledger.save(started.record)
    reconciled = orch.reconcile(started.record.id)
    assert reconciled.lifecycle == ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN
    assert reconciled.lifecycle != ExternalLifecycle.VERIFIED


def test_graph_failure_stays_unverified(tmp_path) -> None:
    graph, _calls = _compile(str(tmp_path / "graph.sqlite"), fail=True)
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    with pytest.raises(RuntimeError, match="analysis failed"):
        orch.start(
            run_id="run-1",
            payload={"requirement": "boom"},
            idempotency_key="idem-1",
            correlation_id="corr-1",
        )
    stored = ledger.get_by_idempotency("project-a", "idem-1")
    assert stored is not None
    assert stored.lifecycle == ExternalLifecycle.DISPATCH_OUTCOME_UNKNOWN
    reconciled = orch.reconcile(stored.id)
    assert reconciled.lifecycle != ExternalLifecycle.VERIFIED


def test_cancel_is_not_pretended(tmp_path) -> None:
    graph, _calls = _compile(str(tmp_path / "graph.sqlite"), with_interrupt=True)
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    started = orch.start(
        run_id="run-1",
        payload={"requirement": "pause"},
        idempotency_key="idem-1",
        correlation_id="corr-1",
    )
    with pytest.raises(UnsupportedCapability):
        orch.cancel(started.record.id)
    assert ledger.get("project-a", started.record.id).lifecycle == ExternalLifecycle.EXTERNAL_SUSPENDED


def test_other_project_cannot_read_execution(tmp_path) -> None:
    graph, _calls = _compile(str(tmp_path / "graph.sqlite"))
    ledger = SqliteLedger(str(tmp_path / "ledger.sqlite"))
    orch = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-a")
    started = orch.start(
        run_id="run-1",
        payload={"requirement": "secret"},
        idempotency_key="idem-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
    )
    assert ledger.get("project-b", started.record.id) is None
    outsider = ExternalOrchestrator(LangGraphAdapter(graph), ledger, project_id="project-b")
    with pytest.raises(KeyError):
        outsider.reconcile(started.record.id)


def test_stream_emits_node_updates(tmp_path) -> None:
    graph, _calls = _compile(str(tmp_path / "graph.sqlite"))
    adapter = LangGraphAdapter(graph)
    events = adapter.stream_events(thread_id="stream-1", payload={"requirement": "trace me"})
    assert events
    assert events[0]["thread_id"] == "stream-1"
