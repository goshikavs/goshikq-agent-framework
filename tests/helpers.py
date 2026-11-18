"""Shared helpers for spawning goshikq-server in integration tests."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:goshikq@127.0.0.1:55432/goshikq")


def find_server() -> Path | None:
    env = os.environ.get("GOSHIKQ_SERVER_BIN") or os.environ.get("AXIOM_SERVER_BIN")
    if env and Path(env).exists():
        return Path(env)

    exe = "goshikq-server.exe" if os.name == "nt" else "goshikq-server"
    triples: list[str] = []
    if os.name == "nt":
        # Prefer the explicit MSVC x64 target when a long-lived process holds target/debug.
        triples = ["x86_64-pc-windows-msvc", "aarch64-pc-windows-msvc"]
    elif sys.platform == "darwin":
        triples = ["aarch64-apple-darwin", "x86_64-apple-darwin"]
    else:
        triples = ["x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu"]

    candidates: list[Path] = []
    for triple in triples:
        candidates.append(ROOT / "target" / triple / "debug" / exe)
        candidates.append(ROOT / "target" / triple / "release" / exe)
    candidates.extend(
        [
            ROOT / "target" / "debug" / exe,
            ROOT / "target" / "release" / exe,
            ROOT / "target" / "x86_64-pc-windows-msvc" / "debug" / "axiom-server.exe",
            ROOT / "target" / "debug" / "axiom-server.exe",
            ROOT / "target" / "debug" / "axiom-server",
        ]
    )
    for p in candidates:
        if p.exists():
            return p
    return None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_server(port: int, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    binary = find_server()
    if binary is None:
        pytest.skip("goshikq-server binary not found")
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": DATABASE_URL,
            "GOSHIKQ_BIND": f"127.0.0.1:{port}",
            "GOSHIKQ_AUTH_MODE": "none",
            "RUST_LOG": env.get("RUST_LOG", "warn"),
        }
    )
    if extra_env:
        env.update(extra_env)
    db_url = env.get("DATABASE_URL", "")
    if db_url.strip().lower() in {"embedded", "goshikq-embedded", "axiom-embedded"} or db_url.startswith("embedded:"):
        # Unique data dir + copied Theseus install (avoids GitHub API 403 on every test).
        dest = ROOT / "target" / "test-pg" / str(port)
        dest.mkdir(parents=True, exist_ok=True)
        cached = ROOT / "target" / "test-pg" / "shared" / "install"
        if cached.exists() and not (dest / "install").exists():
            shutil.copytree(cached, dest / "install")
        env.setdefault("GOSHIKQ_EMBEDDED_PG_PORT", str(free_port()))
        env.setdefault("GOSHIKQ_EMBEDDED_PG_DIR", str(dest))
    log_dir = ROOT / "target" / "test-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"goshikq-server-{port}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    kwargs: dict = {"env": env, "cwd": str(ROOT), "stdout": log_file, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([str(binary)], **kwargs)
    proc._goshikq_log = str(log_path)  # type: ignore[attr-defined]
    proc._goshikq_log_file = log_file  # type: ignore[attr-defined]
    return proc


def wait_ready(url: str, timeout: float = 30.0, proc: subprocess.Popen | None = None) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client() as client:
        while time.monotonic() < deadline:
            if proc is not None and proc.poll() is not None:
                log_path = getattr(proc, "_goshikq_log", None)
                tail = ""
                if log_path and Path(log_path).exists():
                    tail = Path(log_path).read_text(encoding="utf-8", errors="replace")[-2000:]
                raise RuntimeError(
                    f"goshikq-server exited {proc.returncode} before ready at {url}\n{tail}"
                )
            try:
                r = client.get(f"{url}/health", timeout=1.0)
                if r.status_code < 500:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        log_path = getattr(proc, "_goshikq_log", None) if proc is not None else None
        tail = ""
        if log_path and Path(log_path).exists():
            tail = Path(log_path).read_text(encoding="utf-8", errors="replace")[-2000:]
        raise TimeoutError(f"server at {url} did not become ready\n{tail}")


def stop(proc: subprocess.Popen) -> None:
    log_file = getattr(proc, "_goshikq_log_file", None)
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.terminate()
        time.sleep(0.3)
    if log_file is not None:
        try:
            log_file.close()
        except OSError:
            pass
