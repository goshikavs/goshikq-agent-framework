"""LangGraph adapter. The compiled graph is a real LangGraph runnable.

Tested against langgraph 1.2.24. Cancellation is not claimed: LangGraph's
checkpointer can resume a thread, but this adapter has no confirmed-cancel API.
"""

from __future__ import annotations

from typing import Any

from .contract import AdapterCapabilities, ExternalObservation, UnsupportedCapability

LANGGRAPH_TESTED_VERSION = "1.2.24"
ADAPTER_VERSION = "1.1.0-dev"


class LangGraphAdapter:
    framework = "langgraph"
    adapter_version = ADAPTER_VERSION

    def __init__(self, graph: Any, *, framework_version: str = LANGGRAPH_TESTED_VERSION) -> None:
        self._graph = graph
        self.framework_version = framework_version

    def describe_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            native_cancellation=False,
            native_suspend_resume=True,
            persistent_sessions=True,
            streaming=True,
            tool_execution=True,
            human_intervention=True,
            native_checkpointing=True,
            native_tracing=False,
            usage_reporting=False,
            external_run_status=True,
            correlation_ids=True,
        )

    def start(self, *, thread_id: str, payload: dict[str, Any], correlation_id: str) -> ExternalObservation:
        del correlation_id
        result = self._graph.invoke(payload, self._config(thread_id))
        return self._interpret(thread_id, result)

    def get_status(self, *, thread_id: str) -> ExternalObservation:
        snapshot = self._graph.get_state(self._config(thread_id))
        return self._from_snapshot(thread_id, snapshot)

    def resume(self, *, thread_id: str, value: Any) -> ExternalObservation:
        self.describe_capabilities().require(self.framework, "native_suspend_resume")
        from langgraph.types import Command

        result = self._graph.invoke(Command(resume=value), self._config(thread_id))
        return self._interpret(thread_id, result)

    def cancel(self, *, thread_id: str) -> ExternalObservation:
        del thread_id
        raise UnsupportedCapability(self.framework, "native_cancellation")

    def stream_events(self, *, thread_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        self.describe_capabilities().require(self.framework, "streaming")
        events: list[dict[str, Any]] = []
        for chunk in self._graph.stream(payload, self._config(thread_id), stream_mode="updates"):
            events.append({"thread_id": thread_id, "update": _jsonable(chunk)})
        return events

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def _interpret(self, thread_id: str, result: Any) -> ExternalObservation:
        interrupts = _interrupt_values(result)
        payload = _state_payload(result)
        if interrupts:
            return ExternalObservation(
                kind="suspended",
                external_thread_id=thread_id,
                external_run_id=thread_id,
                payload={"state": payload, "interrupts": interrupts},
            )
        return ExternalObservation(
            kind="completed",
            external_thread_id=thread_id,
            external_run_id=thread_id,
            payload={"state": payload},
        )

    def _from_snapshot(self, thread_id: str, snapshot: Any) -> ExternalObservation:
        if snapshot is None:
            return ExternalObservation(kind="unknown", external_thread_id=thread_id, error="no checkpoint")
        values = getattr(snapshot, "values", None) or {}
        nxt = tuple(getattr(snapshot, "next", ()) or ())
        interrupts = _interrupt_values(snapshot)
        tasks = getattr(snapshot, "tasks", None) or ()
        if not values and not nxt and not interrupts and not tasks:
            return ExternalObservation(
                kind="unknown",
                external_thread_id=thread_id,
                error="thread has no checkpoint",
            )
        if interrupts or any(getattr(task, "interrupts", None) for task in tasks):
            return ExternalObservation(
                kind="suspended",
                external_thread_id=thread_id,
                external_run_id=thread_id,
                payload={"state": _jsonable(values), "next": list(nxt)},
            )
        if nxt:
            return ExternalObservation(
                kind="running",
                external_thread_id=thread_id,
                external_run_id=thread_id,
                payload={"state": _jsonable(values), "next": list(nxt)},
            )
        return ExternalObservation(
            kind="completed",
            external_thread_id=thread_id,
            external_run_id=thread_id,
            payload={"state": _jsonable(values)},
        )


def _interrupt_values(result: Any) -> list[Any]:
    raw = getattr(result, "interrupts", None)
    if raw is None and isinstance(result, dict):
        raw = result.get("__interrupt__")
    if not raw:
        tasks = getattr(result, "tasks", None) or ()
        collected = []
        for task in tasks:
            collected.extend(getattr(task, "interrupts", None) or [])
        raw = collected
    values = []
    for item in raw or []:
        values.append(_jsonable(getattr(item, "value", item)))
    return values


def _state_payload(result: Any) -> Any:
    if hasattr(result, "value"):
        return _jsonable(result.value)
    if isinstance(result, dict):
        return {key: _jsonable(value) for key, value in result.items() if key != "__interrupt__"}
    return _jsonable(result)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    return str(value)
