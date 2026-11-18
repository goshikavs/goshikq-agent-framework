"""Optional paid-model test. Default CI must stay deterministic."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("GOSHIKQ_LIVE_LLM") != "1" or not os.environ.get("OPENAI_API_KEY"),
    reason="live LLM tests require GOSHIKQ_LIVE_LLM=1 and OPENAI_API_KEY; not used in default CI",
)


def test_live_llm_placeholder_requires_explicit_opt_in() -> None:
    # This file exists so the gate is explicit. When enabled, add a single
    # bounded hello-agent call with a hard step/cost limit. Do not add it to
    # required CI.
    pytest.skip("no bounded live-LLM scenario wired; keep CI mock-only")
