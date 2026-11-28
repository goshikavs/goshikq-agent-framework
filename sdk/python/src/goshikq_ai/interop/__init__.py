"""Framework interoperability for Goshikq v1.1.0 development.

Public stable release remains v1.0.0 until a later owner-authorized publication.
Framework task success is not business-outcome verification.
"""

from .contract import (
    AdapterCapabilities,
    ExternalObservation,
    FrameworkAdapter,
    UnsupportedCapability,
)
from .langgraph_adapter import LANGGRAPH_TESTED_VERSION, LangGraphAdapter
from .lifecycle import ExternalLifecycle, allow_transition, verify_outcome
from .orchestrator import ExternalOrchestrator, OrchestratorResult

__all__ = [
    "LANGGRAPH_TESTED_VERSION",
    "AdapterCapabilities",
    "ExternalLifecycle",
    "ExternalObservation",
    "ExternalOrchestrator",
    "FrameworkAdapter",
    "LangGraphAdapter",
    "OrchestratorResult",
    "UnsupportedCapability",
    "allow_transition",
    "verify_outcome",
]
