# Framework adapters (v0.4)

v1.0.0 external adapters ingest traces or wrap tools. They do not orchestrate those frameworks.
v1.1.0 development work lives on `feature/v1.1.0-framework-interoperability` and is described in [framework-interoperability.md](framework-interoperability.md). It is not the published stable release.

## LangGraph

`examples/langgraph-refund` compiles a real `StateGraph`. Node functions record OTLP spans (OpenInference / GenAI attributes) and POST them to Goshikq. LangGraph remains the executor. Goshikq does not intercept node side effects.

Requires `pip install langgraph` and a running `goshikq-server`.

## OpenAI Agents SDK

`examples/openai-agents-refund` uses the documented `TracingProcessor` hooks when `openai-agents` is installed. Without the package it emits the same OTLP shape from a mock path so the mapping can be tested.

Private SDK internals are not used.

## Capability matrix

See [framework-capability-manifest.md](framework-capability-manifest.md) and `GET /api/v1/capabilities`.
