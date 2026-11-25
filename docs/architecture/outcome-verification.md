# Outcome verification

Goshikq splits five independent fields. Do not treat any one as a proxy for another.

| Field | Owner | Example pending refund |
|---|---|---|
| Execution status | Run state machine | `WAITING_FOR_EXTERNAL_STATE` |
| Tool status | Tool invocation row | `SUCCEEDED` (processor accepted) |
| External business-operation status | Authoritative system via snapshot | `PENDING_SETTLEMENT` / `accepted` |
| Goal satisfaction | Success predicate on snapshot | `false` until `order.status=refunded` and `refund.status=settled` |
| Goal verification status | Verifier / predicate result | `INCONCLUSIVE` while waiting; `VERIFIED` only after settlement |

An agent loop writes `COMPLETED` together with `verification_status=VERIFIED` only when the success predicate is true against a `StateProvider` snapshot, in the same lease-fenced row update. A tool HTTP 200 / `accepted: true`, a model claim, or a tool result that says to mark the goal verified is not sufficient.

A workflow graph can reach `COMPLETED` without `VERIFIED` when it has no verify node that accepted authoritative state (`verification_policy=none` stays `NOT_EVALUATED`). `result.verified` in the SDKs is true only when status is `COMPLETED` and verification is `VERIFIED`.

`VERIFIED` is a point-in-time record. A later change in the external system does not rewrite that row. A new run has to observe the new state. Evidence freshness is the snapshot version and `observed_at` captured for that decision, not a promise that the outside world stays there.

A stale lease holder cannot stamp `VERIFIED`. The completion update checks `lease_owner`, `lease_generation`, and `lease_expires_at`. Other verification writes from the executor use the same lease check and are rejected after a steal.

Current business-operation status is projected from `tool_invocations.business_operation_status` (updated as the journal observes settlement). Past `action-verify` events are not rewritten if they still say `accepted`.

Live delayed-settlement run `01a185c1-c575-73c1-9e2b-54d069ffad5b` (2026-10-28): `GET /verification` returned `tool_status=SUCCEEDED`, `business_operation_status=SETTLED`, `verification_status=VERIFIED`, `goal_satisfied=true`. The earlier action evidence row remains `INCONCLUSIVE` (`order.status=refund_pending`, `refund.status=accepted`). Studio rendered both.

Never-settles run `01a185c1-f6e5-7130-acc0-348a15ceab9a`: `UNVERIFIED` / `INCONCLUSIVE`, `tool_status=SUCCEEDED`, `business_operation_status=PENDING_SETTLEMENT`.

## Canonical contract

`GET /api/v1/runs/{id}/verification` includes `outcome`:

```json
{
  "execution_status": "UNVERIFIED",
  "tool_status": "SUCCEEDED",
  "business_operation_status": "PENDING_SETTLEMENT",
  "goal_satisfied": false,
  "verification_status": "INCONCLUSIVE",
  "evidence_source": "simulated-orders+processor",
  "evidence_version": "...",
  "observed_at": "...",
  "verifier": "order.status+refund.status"
}
```

Evidence records source, version, observation time, and verifier identity when the snapshot/verifier supplied them.

## Python

`VerifierResult.waiting(...)` sets `status=INCONCLUSIVE`, `wait=true`, and `business_operation_status`. The runtime then enters `WAITING_FOR_EXTERNAL_STATE` instead of failing the action or burning `max_steps`.

## Studio

The verification page renders the five-way contract. Pending settlement and `INCONCLUSIVE` use amber badges. Historical replay does not execute tools.
