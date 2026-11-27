# Installs a published Goshikq GitHub Release archive after checking SHA256SUMS.
# Does not request administrator rights. Does not publish or modify a release.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Version v1.0.0

[CmdletBinding()]
param(
    [string]$Version = "v1.0.0",
    [string]$Dest = ""
)

$ErrorActionPreference = "Stop"
$repo = "goshikavs/goshikq-agent-framework"

function Resolve-GoshikqPlatform([string]$Arch) {
    switch ($Arch) {
        "X64" { return "windows-amd64" }
        "Arm64" { return "windows-arm64" }
        default { throw "Unsupported Windows architecture '$Arch'. Supported: X64, Arm64 (experimental)." }
    }
}

function Test-GoshikqSha256([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
    $want = $Expected.ToLowerInvariant()
    if ($actual -ne $want) {
        throw "SHA256 mismatch for ${Path}: expected $want actual $actual"
    }
    return $actual
}

# Dot-sourcing loads Test-GoshikqSha256 for tests and does not download a release.
if ($MyInvocation.InvocationName -eq '.') {
    return
}

function Write-GoshikqQuickstart([string]$Directory) {
    $quickstart = @'
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
'@
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Join-Path $Directory 'hello_agent.py'), $quickstart, $utf8)
}

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
$os = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
if ($os -notmatch "Windows") {
    Fail "install.ps1 is for Windows. On macOS or Linux run scripts/install.sh."
}
try {
    $platform = Resolve-GoshikqPlatform $arch
} catch {
    Fail $_.Exception.Message
}
$ext = "zip"
if ($platform -eq "windows-arm64") {
    Write-Warning "Windows ARM64 is experimental and is not a supported v1.0 platform."
}

$tag = $Version
if ($tag -notmatch "^v") { $tag = "v$tag" }
$ver = $tag.TrimStart("v")
$asset = "goshikq-$ver-$platform.$ext"
$base = "https://github.com/$repo/releases/download/$tag"
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("goshikq-install-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $work | Out-Null

try {
    $sumsPath = Join-Path $work "SHA256SUMS"
    $archivePath = Join-Path $work $asset
    Write-Host "Downloading $base/SHA256SUMS"
    Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $sumsPath -UseBasicParsing
    Write-Host "Downloading $base/$asset"
    Invoke-WebRequest -Uri "$base/$asset" -OutFile $archivePath -UseBasicParsing

    $line = Get-Content $sumsPath | Where-Object { $_ -match [regex]::Escape($asset) } | Select-Object -First 1
    if (-not $line) { Fail "SHA256SUMS has no entry for $asset" }
    $expected = ($line -split "\s+")[0]
    try {
        $actual = Test-GoshikqSha256 -Path $archivePath -Expected $expected
    } catch {
        Fail $_.Exception.Message
    }
    Write-Host "SHA256 ok $actual"

    if (-not $Dest) {
        $Dest = Join-Path $env:LOCALAPPDATA "goshikq\$tag"
    }
    if (Test-Path $Dest) { Remove-Item -LiteralPath $Dest -Recurse -Force }
    New-Item -ItemType Directory -Path $Dest | Out-Null
    Expand-Archive -Path $archivePath -DestinationPath $Dest -Force
    $server = Get-ChildItem -Path $Dest -Recurse -Filter "goshikq-server.exe" | Select-Object -First 1
    if (-not $server) { Fail "Archive did not contain goshikq-server.exe" }
    $bin = $server.DirectoryName
    Write-Host "Installed to $bin"
    Write-Host "Add to the user PATH for this session:"
    Write-Host "  `$env:PATH = '$bin;' + `$env:PATH"
    Write-Host "Then run: goshikq-server.exe"
    Write-GoshikqQuickstart $bin
    Write-Host "First run, after /health is ok. This file does not need the git repository:"
    Write-Host "  python '$bin\hello_agent.py'"
    Write-Host "Manual alternative: download $asset and SHA256SUMS from $base and compare the hash yourself."
}
finally {
    if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}
