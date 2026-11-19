#!/usr/bin/env python3
"""Smoke-test an extracted Goshikq release archive (not target/debug)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def extract(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip" or archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(dest)
    bins = list(dest.rglob("goshikq-server")) + list(dest.rglob("goshikq-server.exe"))
    if not bins:
        raise SystemExit(f"archive {archive} has no goshikq-server")
    return bins[0].parent


def http_json(url: str, timeout: float = 2.0) -> dict:
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (URLError, OSError, TimeoutError):
        return False


def port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        try:
            sock.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def kill_windows_listeners(port: int) -> None:
    """Theseus may leave postgres.exe listening after goshikq-server exits."""
    netstat = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
    pids: set[str] = set()
    token = f":{port}"
    for line in netstat.stdout.splitlines():
        if token not in line or "LISTENING" not in line.upper():
            continue
        pid = line.split()[-1]
        if pid.isdigit() and pid != "0":
            pids.add(pid)
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, text=True, check=False)


def wait_ports_free(ports: list[int], seconds: float = 40) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if os.name == "nt":
            for port in ports:
                if port_listening(port):
                    kill_windows_listeners(port)
        if not any(port_listening(p) for p in ports):
            return
        time.sleep(0.5)
    busy = [p for p in ports if port_listening(p)]
    raise SystemExit(f"ports still in use after shutdown: {busy}")


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        if os.name == "nt":
            # Theseus PostgreSQL is a child process. Terminate() leaves it
            # holding the data directory on Windows; /T kills the tree.
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
        else:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
    wait_ports_free([17400, 55439])


def wait_ready(base: str, proc: subprocess.Popen, log: Path, seconds: int = 180) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"goshikq-server exited {proc.returncode}\n{log.read_text(encoding='utf-8', errors='replace')[-4000:]}")
        if http_ok(f"{base}/ready"):
            return
        time.sleep(2)
    raise SystemExit(f"not ready\n{log.read_text(encoding='utf-8', errors='replace')[-4000:]}")


def find_cli(root: Path) -> Path:
    hits = list(root.glob("goshikq.exe")) + list(root.glob("goshikq"))
    if not hits:
        raise SystemExit("CLI binary missing from archive")
    return hits[0]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True)
    p.add_argument("--bind", default="127.0.0.1:17400")
    p.add_argument("--skip-agent", action="store_true")
    args = p.parse_args()
    archive = Path(args.archive).resolve()
    work = Path(tempfile.mkdtemp(prefix="goshikq-rc-smoke-"))
    log = work / "server.log"
    data = work / "pg"
    try:
        extracted = extract(archive, work / "extract")
        server = next(
            p for p in [extracted / "goshikq-server.exe", extracted / "goshikq-server"] if p.exists()
        )
        cli = find_cli(extracted)
        if os.name != "nt":
            for b in (server, cli):
                b.chmod(b.stat().st_mode | 0o111)

        help_out = subprocess.run([str(cli), "--help"], capture_output=True, text=True, timeout=30)
        if help_out.returncode != 0:
            raise SystemExit(help_out.stdout + help_out.stderr)
        ver_out = subprocess.run([str(cli), "--version"], capture_output=True, text=True, timeout=30)
        print("cli --version:", ver_out.stdout.strip() or ver_out.stderr.strip())
        if "goshikq" not in (ver_out.stdout + ver_out.stderr + help_out.stdout).lower():
            raise SystemExit("CLI help/version did not mention goshikq")
        srv_help = subprocess.run([str(server), "--help"], capture_output=True, text=True, timeout=30)
        if srv_help.returncode != 0:
            raise SystemExit(srv_help.stdout + srv_help.stderr)

        env = os.environ.copy()
        env["DATABASE_URL"] = "embedded"
        env["GOSHIKQ_AUTH_MODE"] = "none"
        env["GOSHIKQ_BIND"] = args.bind
        env["GOSHIKQ_EMBEDDED_PG_DIR"] = str(data)
        env["GOSHIKQ_EMBEDDED_PG_PORT"] = "55439"
        env["GOSHIKQ_RUNTIME_URL"] = f"http://{args.bind}"
        base = f"http://{args.bind}"

        def start() -> subprocess.Popen:
            lf = log.open("ab")
            return subprocess.Popen(
                [str(server)],
                cwd=str(extracted),
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
            )

        proc = start()
        wait_ready(base, proc, log)
        health = http_json(f"{base}/health")
        print("health:", json.dumps(health, sort_keys=True))
        if health.get("version") not in {"1.0.0-rc.1", env.get("EXPECTED_VERSION", "1.0.0-rc.1")}:
            print("warning: /health version", health.get("version"), file=sys.stderr)

        if not args.skip_agent:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", "-e", str(ROOT / "sdk" / "python"), "httpx", "pytest"],
                cwd=str(ROOT),
            )
            agent = subprocess.run(
                [sys.executable, str(ROOT / "examples" / "hello-agent" / "main.py")],
                cwd=str(ROOT / "examples" / "hello-agent"),
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            print(agent.stdout)
            if agent.returncode != 0:
                raise SystemExit(agent.stderr or agent.stdout)

        import uuid

        definition = {
            "name": f"rc-smoke-{uuid.uuid4().hex[:8]}",
            "version": 1,
            "nodes": [
                {"id": "start", "kind": "start", "label": "s", "config": {}},
                {"id": "echo", "kind": "tool", "label": "echo", "config": {"tool": "echo", "handler": "echo"}},
                {"id": "end", "kind": "end", "label": "e", "config": {}},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "echo"},
                {"id": "e2", "source": "echo", "target": "end"},
            ],
            "max_steps": 8,
        }
        import urllib.request

        def post(path: str, payload: dict | None = None) -> dict:
            data = None if payload is None else json.dumps(payload).encode()
            headers = {"content-type": "application/json"} if data is not None else {}
            req = urllib.request.Request(
                f"{base}{path}",
                data=data,
                headers=headers,
                method="POST",
            )
            with urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else {}

        created = post("/api/v1/workflows", {"definition": definition, "draft": True})
        wf_id = created["id"]
        post(f"/api/v1/workflows/{wf_id}/publish")
        started = post(f"/api/v1/workflows/{wf_id}/run", {"input": {"n": 1}})
        run_id = started["run_id"]
        deadline = time.time() + 60
        status = None
        while time.time() < deadline:
            run = http_json(f"{base}/api/v1/runs/{run_id}")
            status = run.get("status")
            if status in {"COMPLETED", "FAILED", "UNVERIFIED", "TIMED_OUT"}:
                break
            time.sleep(0.2)
        print("workflow status:", status, "run_id:", run_id)
        if status != "COMPLETED":
            raise SystemExit(f"durable workflow did not complete: {status}")

        stop(proc)
        print("graceful shutdown exit", proc.returncode)
        proc = start()
        wait_ready(base, proc, log)
        recovered = http_json(f"{base}/api/v1/runs/{run_id}")
        print("recovered run status:", recovered.get("status"))
        if recovered.get("status") != "COMPLETED":
            raise SystemExit(f"run not durable after restart: {recovered}")
        stop(proc)
        print("SMOKE_OK", archive.name)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
