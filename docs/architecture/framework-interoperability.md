# Framework interoperability (v1.1.0 development)

This document describes work on `feature/v1.1.0-framework-interoperability`.
The published stable release remains **v1.0.0**. Nothing in this document is a
stable-release claim.

Positioning: **Build agents. Coordinate frameworks. Verify outcomes.**
Goshikq does not replace LangGraph, Mastra, CrewAI, LlamaIndex, smolagents, or
Microsoft Agent Framework. It coordinates them and keeps business-outcome
verification independent of a framework's own success report.

## Current-state architecture (v1.0.0)

The Rust runtime owns runs, leases, the action journal, evidence, and goal
verification. Python and TypeScript SDKs are native workers. Parent and child
runs are the multi-agent model (`docs/architecture/multi-agent.md`).

External frameworks in v1.0.0 are observational:

| Path | What it does | What it does not do |
|---|---|---|
| `langgraph` OTLP ingest | Stores spans from a graph Goshikq does not execute | Does not resume, cancel, or verify the graph |
| `openai-agents` tracing hooks | Same, for that SDK's documented tracer | Does not run `Runner.run` |
| MCP | Wraps tools under an allowlist | Tool text is not business state |
| A2A | JSON-RPC subset: card, send, get, cancel | Remote completion is not parent verification |

`DispatchState` on tool invocations already separates accepted writes from
confirmed outcomes. External framework runs need their own lifecycle because a
graph thread is not a Goshikq tool call.

## Integration architecture on this branch

```
Business application
        |
Goshikq runtime (runs, leases, evidence, verification)
        |
External execution record (project-scoped identity)
        |
Framework adapter (capability negotiation)
        |
LangGraph / future adapters
        |
External tools and systems
        |
Independent evidence
        |
Goshikq verification gate
```

The adapter does not become a second orchestrator. It executes the foreign
runtime and reports observations. Goshikq stores identity and applies the
lifecycle. `VERIFIED` is not an observation.

### Adapter operations

Implemented on the Python protocol (`goshikq_ai.interop`):

| Operation | Behavior when unsupported |
|---|---|
| `describe_capabilities` | Required |
| `start` | Required |
| `get_status` | Required for reconciliation |
| `resume` | `UnsupportedCapability` |
| `cancel` | `UnsupportedCapability`; never stored as `CANCELLED` |
| `stream_events` | `UnsupportedCapability` |

`getResult` and `getEvidence` are the observation payload plus the ledger.
Usage is stored only when the adapter reports it. LangGraph 1.2.24 does not
report token usage for these deterministic graphs, so usage support stays false.

### Identity

Each execution persists:

- Goshikq execution id and run id
- project id (the tenant boundary used by the runtime)
- optional tenant, parent run, and task ids
- framework name, adapter version, framework version
- external run id and thread id
- correlation id, trace id, idempotency key, dispatch id

The SDK ledger is SQLite. The server table is `external_executions`
(migration `0010`). Both lookups include `project_id`. A different project
gets no row, not another tenant's payload.

Server routes:

- `POST /api/v1/runs/{id}/external-executions`
- `GET /api/v1/runs/{id}/external-executions`
- `GET /api/v1/external-executions/{id}`
- `POST /api/v1/external-executions/{id}/transition`
- `POST /api/v1/external-executions/{id}/verify`

The transition route rejects `VERIFIED`, `VERIFICATION_FAILED`, and
`VERIFICATION_INCONCLUSIVE`. The verify route rejects evidence whose source
equals the framework name.

### Lifecycle

`NOT_DISPATCHED` → `DISPATCH_IN_PROGRESS` → one of `EXTERNAL_RUNNING`,
`EXTERNAL_SUSPENDED`, `EXTERNAL_COMPLETED`, `EXTERNAL_FAILED`,
`DISPATCH_OUTCOME_UNKNOWN`, or `RECONCILIATION_REQUIRED`.

`EXTERNAL_COMPLETED` can move to `AWAITING_VERIFICATION`. Only that state can
become `VERIFIED` or `VERIFICATION_INCONCLUSIVE`, and only from evidence that
is not the framework's own claim.

`CANCELLED` is reachable only from `CANCEL_REQUESTED`, and only when
`native_cancellation` is true. LangGraph's tested adapter sets that flag false.

Unknown checkpoints stay `DISPATCH_OUTCOME_UNKNOWN`. They are not completed.

### Checkpoint ownership

LangGraph's checkpointer owns graph state. Goshikq's ledger owns dispatch
identity and the verification gate. Resume uses LangGraph `Command(resume=...)`
on the same `thread_id`. Goshikq does not copy the checkpoint into its own
run checkpoint.

### Security

- Project id is the isolation key on every read and write.
- Framework success text cannot pass `verify_outcome`.
- Cancellation without a confirmed observation is an error, not `CANCELLED`.
- A duplicate idempotency key returns the existing row and does not invoke the graph again.
- Prompt injection is unchanged: model text is not authoritative state.
- smolagents code execution is not implemented. It must not be an unrestricted in-process exec.

## Compatibility matrix

Capabilities below are `supported` only where a test in this branch executed the real library.
`not_implemented` means no adapter has been written. Do not read that as a planned guarantee.

| Framework | Language | Tested version | Adapter | Start | Status | Resume | Cancel | Stream | Recovery | Evidence gate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LangGraph | Python | 1.2.24 | `LangGraphAdapter` | tested | tested | tested (`interrupt` / `Command`) | unsupported, rejected | tested | tested with SqliteSaver across a new process object | tested; framework source rejected | Does not replace LangGraph's checkpointer |
| LangGraph OTLP | Python | v1.0.0 ingest path | existing span import | n/a | n/a | unsupported | unsupported | n/a | n/a | partial only with an explicit snapshot attribute | Unchanged v1.0.0 behavior |
| Mastra | TypeScript | — | not_implemented | — | — | — | — | — | — | — | Not started |
| CrewAI | Python | — | not_implemented | — | — | — | — | — | — | — | Not started |
| LlamaIndex Workflows | — | — | not_implemented | — | — | — | — | — | — | — | Language choice not made yet |
| smolagents | Python | — | not_implemented | — | — | — | — | — | — | — | Code execution must be isolated before any adapter is called supported |
| Microsoft Agent Framework | Python / .NET | — | not_implemented | — | — | — | — | — | — | — | .NET is not supported |
| Native Goshikq | Rust + SDKs | v1.0.0 | worker protocol | supported | supported | supported | supported | supported | supported | supported | Existing runtime |

## Test plan

| Area | Where | Status on this branch |
|---|---|---|
| Lifecycle edges and verification gate | `goshikq-protocol` `interop` tests | Written; run in the session that added them |
| LangGraph success, duplicate dispatch, interrupt/resume, restart, unknown thread, failure, cancel rejection, project isolation, stream | `sdk/python/tests/test_langgraph_interop.py` | Passing locally against langgraph 1.2.24 |
| PostgreSQL migration 0010 against a live server | not written as an integration test yet | NOT_RUN |
| Mastra, CrewAI, LlamaIndex, smolagents, Microsoft Agent Framework, hybrid workflow | — | NOT_RUN |
| Studio cross-framework panels | — | NOT_RUN |

## Known limitations

- The Python orchestrator and the Rust routes share the lifecycle rules, but the LangGraph tests use the SQLite ledger, not HTTP against `goshikq-server`.
- Native LangGraph cancellation is unsupported.
- Tracing correlation is an id on the record. This adapter does not export OTEL spans itself (`native_tracing` is false).
- Hybrid multi-framework workflows are not implemented.
- v1.1.0 is not published. v1.0.0 remains the stable release.
