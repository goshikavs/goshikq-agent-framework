"""Deterministic LangGraph requirements step coordinated by Goshikq.

This is v1.1.0 development code. It is not the v1.0.0 stable install path.
Requires: pip install "langgraph>=1.2.24,<1.3" "langgraph-checkpoint-sqlite>=3.1.3,<4"

The graph runs locally. No cloud model key is used.
A completed graph is AWAITING_VERIFICATION until an independent evidence source
passes. The framework name is not that source.
"""

from __future__ import annotations

import sqlite3
import tempfile
from typing import TypedDict

from goshikq_ai.interop import ExternalLifecycle, ExternalOrchestrator, LangGraphAdapter
from goshikq_ai.interop.ledger import SqliteLedger
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class State(TypedDict, total=False):
    requirement: str
    analysis: str


def analyze(state: State) -> dict[str, str]:
    return {"analysis": state["requirement"].strip().upper()}


def main() -> None:
    directory = tempfile.mkdtemp(prefix="goshikq-langgraph-")
    conn = sqlite3.connect(f"{directory}/graph.sqlite", check_same_thread=False)
    builder = StateGraph(State)
    builder.add_node("analyze", analyze)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    graph = builder.compile(checkpointer=SqliteSaver(conn))
    orchestrator = ExternalOrchestrator(
        LangGraphAdapter(graph),
        SqliteLedger(f"{directory}/ledger.sqlite"),
        project_id="local-demo",
    )
    started = orchestrator.start(
        run_id="demo-run",
        payload={"requirement": "ship the fix"},
        idempotency_key="demo-1",
        correlation_id="demo-correlation",
    )
    print("framework lifecycle", started.record.lifecycle.value)
    print("analysis", started.record.result["state"]["analysis"])
    if started.record.lifecycle != ExternalLifecycle.EXTERNAL_COMPLETED:
        raise SystemExit("expected the graph to complete")
    orchestrator.accept_for_verification(started.record.id)
    try:
        orchestrator.verify(
            started.record.id,
            predicate_passed=True,
            evidence_source="langgraph",
            evidence_fingerprint="framework-claim",
        )
    except ValueError as exc:
        print("framework claim rejected:", exc)
    else:
        raise SystemExit("framework claim must not verify")
    verified = orchestrator.verify(
        started.record.id,
        predicate_passed=True,
        evidence_source="local-test-runner",
        evidence_fingerprint="demo-ok",
    )
    print("verification", verified.lifecycle.value)


if __name__ == "__main__":
    main()
