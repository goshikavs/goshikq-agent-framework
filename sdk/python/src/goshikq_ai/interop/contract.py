"""Framework-agnostic adapter contract.

Adapters wrap a framework's own runtime. Missing capabilities raise
:class:`UnsupportedCapability` instead of reporting a successful no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class UnsupportedCapability(RuntimeError):
    def __init__(self, framework: str, capability: str) -> None:
        self.framework = framework
        self.capability = capability
        super().__init__(f"{framework} does not support {capability}")


@dataclass(frozen=True)
class AdapterCapabilities:
    native_cancellation: bool = False
    native_suspend_resume: bool = False
    persistent_sessions: bool = False
    streaming: bool = False
    tool_execution: bool = False
    human_intervention: bool = False
    native_checkpointing: bool = False
    native_tracing: bool = False
    usage_reporting: bool = False
    external_run_status: bool = False
    correlation_ids: bool = True

    def require(self, framework: str, name: str) -> None:
        if not getattr(self, name):
            raise UnsupportedCapability(framework, name)

    def to_dict(self) -> dict[str, bool]:
        return {
            "native_cancellation": self.native_cancellation,
            "native_suspend_resume": self.native_suspend_resume,
            "persistent_sessions": self.persistent_sessions,
            "streaming": self.streaming,
            "tool_execution": self.tool_execution,
            "human_intervention": self.human_intervention,
            "native_checkpointing": self.native_checkpointing,
            "native_tracing": self.native_tracing,
            "usage_reporting": self.usage_reporting,
            "external_run_status": self.external_run_status,
            "correlation_ids": self.correlation_ids,
        }


@dataclass
class ExternalObservation:
    """What the adapter could actually read. `unknown` is never success."""

    kind: str
    external_run_id: str | None = None
    external_thread_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    usage: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        allowed = {"unknown", "running", "suspended", "completed", "failed", "cancel_confirmed"}
        if self.kind not in allowed:
            raise ValueError(f"unknown observation kind {self.kind}")


class FrameworkAdapter(Protocol):
    framework: str
    adapter_version: str
    framework_version: str

    def describe_capabilities(self) -> AdapterCapabilities: ...

    def start(self, *, thread_id: str, payload: dict[str, Any], correlation_id: str) -> ExternalObservation: ...

    def get_status(self, *, thread_id: str) -> ExternalObservation: ...

    def resume(self, *, thread_id: str, value: Any) -> ExternalObservation: ...

    def cancel(self, *, thread_id: str) -> ExternalObservation: ...

    def stream_events(self, *, thread_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
