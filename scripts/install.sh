#!/bin/sh
# Install a published Goshikq GitHub Release archive after checking SHA256SUMS.
# No root required. Does not publish or modify a release.
# Usage: sh scripts/install.sh --version v1.0.0
set -eu

version="v1.0.0"
dest=""
repo="goshikavs/goshikq-agent-framework"

while [ $# -gt 0 ]; do
  case "$1" in
    --version) version="$2"; shift 2 ;;
    --dest) dest="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

fail() { echo "$1" >&2; exit 1; }

write_quickstart() {
  cat > "$1/hello_agent.py" << 'END_GOSHIKQ_QUICKSTART'
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
END_GOSHIKQ_QUICKSTART
}

check_sha() {
  file="$1"
  expected="$2"
  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$file" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$file" | awk '{print $1}')
  else
    fail "Need sha256sum or shasum to verify the archive."
  fi
  if [ "$actual" != "$expected" ]; then
    fail "SHA256 mismatch for ${file}: expected ${expected} actual ${actual}"
  fi
  echo "SHA256 ok ${actual}"
}

# CI sets these to prove a bad digest is rejected. A normal install does not.
if [ -n "${GOSHIKQ_CHECK_FILE:-}" ]; then
  check_sha "$GOSHIKQ_CHECK_FILE" "${GOSHIKQ_CHECK_EXPECTED:?GOSHIKQ_CHECK_EXPECTED is required}"
  exit 0
fi

os=$(uname -s)
machine=$(uname -m)
case "$os:$machine" in
  Linux:x86_64) platform="linux-amd64"; ext="tar.gz" ;;
  Linux:aarch64|Linux:arm64) platform="linux-arm64"; ext="tar.gz" ;;
  Darwin:x86_64) platform="macos-amd64"; ext="tar.gz" ;;
  Darwin:arm64) platform="macos-arm64"; ext="tar.gz" ;;
  *) fail "Unsupported platform ${os} ${machine}. Supported: Linux x86_64/arm64, macOS x86_64/arm64. Windows: scripts/install.ps1." ;;
esac

case "$version" in
  v*) tag="$version" ;;
  *) tag="v$version" ;;
esac
ver=$(printf '%s' "$tag" | sed 's/^v//')
asset="goshikq-${ver}-${platform}.${ext}"
base="https://github.com/${repo}/releases/download/${tag}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "Downloading ${base}/SHA256SUMS"
curl -fsSL "${base}/SHA256SUMS" -o "${work}/SHA256SUMS"
echo "Downloading ${base}/${asset}"
curl -fsSL "${base}/${asset}" -o "${work}/${asset}"

expected=$(awk -v name="$asset" '$2 == name || $2 == ("./" name) { print $1; exit }' "${work}/SHA256SUMS")
if [ -z "$expected" ]; then
  fail "SHA256SUMS has no entry for ${asset}"
fi
check_sha "${work}/${asset}" "$expected"

if [ -z "$dest" ]; then
  dest="${HOME}/.local/share/goshikq/${tag}"
fi
rm -rf "$dest"
mkdir -p "$dest"
tar -xzf "${work}/${asset}" -C "$dest"
server=$(find "$dest" -type f -name goshikq-server | head -n 1)
if [ -z "$server" ]; then
  fail "Archive did not contain goshikq-server"
fi
bin=$(dirname "$server")
chmod 755 "$bin/goshikq-server" "$bin/goshikq" 2>/dev/null || true
echo "Installed to ${bin}"
echo "Add to PATH for this shell:"
echo "  export PATH=\"${bin}:\$PATH\""
echo "Then run: goshikq-server"
write_quickstart "$bin"
echo "First run, after /health is ok. This file does not need the git repository:"
echo "  python3 \"${bin}/hello_agent.py\""
echo "Manual alternative: download ${asset} and SHA256SUMS from ${base} and compare the hash yourself."
