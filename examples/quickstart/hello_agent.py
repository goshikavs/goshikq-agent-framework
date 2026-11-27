#!/usr/bin/env python3
"""First Goshikq agent. Uses only the Python standard library.

The runtime must already be listening. Default URL: http://127.0.0.1:7400.
GOSHIKQ_AUTH_MODE=none is valid only for that loopback process.

This file records a greeting, then asks the runtime to evaluate the goal
against that store. A model sentence is not the outcome.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("GOSHIKQ_RUNTIME_URL", "http://127.0.0.1:7400").rstrip("/")
GREETINGS: dict[str, str] = {}
TURNS = 0


def request(method: str, path: str, body: dict | None = None, timeout: float = 30) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        ENDPOINT + path,
        data=data,
        method=method,
        headers={"content-type": "application/json", "user-agent": "goshikq-quickstart/1.0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"cannot reach {ENDPOINT}: {exc.reason}") from exc
    if not raw:
        return {}
    return json.loads(raw)


def dotted(state: dict, path: str):
    cur = state
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def handle(kind: str, payload: dict) -> dict:
    global TURNS
    if kind == "model.generate":
        TURNS += 1
        if TURNS == 1:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "record_greeting",
                        "arguments": {"name": "Ada", "message": "Hello, Ada!"},
                    }
                ],
                "usage": {"input_tokens": 12, "output_tokens": 8},
                "finish_reason": "tool_calls",
                "model": "mock/deterministic",
                "provider": "mock",
            }
        return {
            "content": "Greeted Ada.",
            "tool_calls": [],
            "usage": {"input_tokens": 16, "output_tokens": 4},
            "finish_reason": "stop",
            "model": "mock/deterministic",
            "provider": "mock",
        }
    if kind == "tool.execute":
        if payload.get("tool_name") != "record_greeting":
            raise SystemExit(f"unexpected tool {payload.get('tool_name')}")
        args = payload.get("arguments") or {}
        GREETINGS[str(args["name"])] = str(args["message"])
        return {"output": {"stored": True, "name": args["name"]}}
    if kind == "state.snapshot":
        return {
            "state": {"greetings": dict(GREETINGS)},
            "version": str(len(GREETINGS)),
            "source": "greetings-memory",
        }
    if kind == "goal.evaluate":
        state = payload.get("state") or {}
        greeting = dotted(state, "greetings.Ada")
        one = isinstance(state.get("greetings"), dict) and len(state["greetings"]) <= 1
        result = {
            "invariants": [{"name": "no_more_than_one_greeting", "satisfied": one}],
            "evidence": {"source": "greetings-memory", "version": payload.get("state_version")},
        }
        if payload.get("evaluate_success"):
            ok = isinstance(greeting, str) and "Ada" in greeting
            result["success"] = ok
            result["reason"] = "Ada has a stored greeting" if ok else "greeting missing"
            result["evidence"].update({"predicate": "ada_was_greeted", "actual": greeting})
        return result
    raise SystemExit(f"unexpected worker request {kind}")


def main() -> int:
    created = request(
        "POST",
        "/api/v1/runs",
        {
            "agent": {
                "name": "hello-agent",
                "model": "mock/deterministic",
                "instructions": "Greet the person named in the input.",
                "tools": [
                    {
                        "name": "record_greeting",
                        "description": "Store a greeting for name.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "message": {"type": "string"},
                            },
                            "required": ["name", "message"],
                            "additionalProperties": False,
                        },
                        "effect": "IDEMPOTENT_WRITE",
                        "risk": "low",
                        "idempotent": True,
                    }
                ],
            },
            "goal": {
                "description": "Ada has been greeted exactly once",
                "success_predicate": "ada_was_greeted",
                "invariants": ["no_more_than_one_greeting"],
                "verification_policy": "required",
                "max_steps": 4,
            },
            "input": {"name": "Ada"},
            "has_state_provider": True,
            "source_framework": "goshikq",
            "metadata": {"protocol_version": "1.0", "quickstart": "stdlib"},
        },
    )
    run_id = created["run_id"]
    for _ in range(40):
        poll = request("POST", f"/api/v1/runs/{run_id}/worker/poll?timeout_ms=5000", {}, timeout=30)
        req = poll.get("request")
        if req is not None:
            result = handle(req["kind"], req.get("payload") or {})
            request(
                "POST",
                f"/api/v1/runs/{run_id}/worker/respond",
                {"request_id": req["request_id"], "ok": True, "result": result},
            )
        if poll.get("terminal"):
            break
    else:
        raise SystemExit("run did not finish")
    run = request("GET", f"/api/v1/runs/{run_id}")
    report = request("GET", f"/api/v1/runs/{run_id}/verification")
    outcome = report.get("outcome") or {}
    print(f"run_id:        {run_id}")
    print(f"status:        {run.get('status')}")
    print(f"verification:  {run.get('verification_status')}")
    print(f"evidence:      {outcome.get('evidence_source')}@{outcome.get('evidence_version')}")
    verified = run.get("status") == "COMPLETED" and run.get("verification_status") == "VERIFIED"
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
