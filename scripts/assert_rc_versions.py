#!/usr/bin/env python3
"""Require consistent v1.0.0-rc.1 package versions across ecosystems.

Cargo/npm use SemVer prerelease `1.0.0-rc.1`.
Python uses PEP 440 `1.0.0rc1`.
Do not substitute one string into every ecosystem.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARGO = "1.0.0-rc.1"
NPM = "1.0.0-rc.1"
PY = "1.0.0rc1"

errors: list[str] = []


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


def cargo_workspace_version() -> str:
    data = tomllib.loads(read(ROOT / "Cargo.toml"))
    return data["workspace"]["package"]["version"]


def pyproject_version() -> str:
    data = tomllib.loads(read(ROOT / "sdk" / "python" / "pyproject.toml"))
    return data["project"]["version"]


def json_version(path: Path) -> str:
    return json.loads(read(path))["version"]


def main() -> int:
    check(cargo_workspace_version() == CARGO, f"Cargo.toml workspace.package.version must be {CARGO}")
    check(pyproject_version() == PY, f"sdk/python/pyproject.toml version must be {PY} (PEP 440)")
    check(
        '__version__ = "1.0.0rc1"' in read(ROOT / "sdk" / "python" / "src" / "goshikq_ai" / "_version.py"),
        "Python _version.py must match PEP 440 1.0.0rc1",
    )
    npm_paths = [
        ROOT / "package.json",
        ROOT / "sdk" / "typescript" / "package.json",
        ROOT / "apps" / "studio" / "package.json",
        ROOT / "apps" / "website" / "package.json",
    ]
    for p in npm_paths:
        check(json_version(p) == NPM, f"{p.relative_to(ROOT)} version must be {NPM}")
    ts_ver = read(ROOT / "sdk" / "typescript" / "src" / "version.ts")
    check(f'"{NPM}"' in ts_ver, "sdk/typescript/src/version.ts must export 1.0.0-rc.1")
    site = read(ROOT / "apps" / "website" / "src" / "lib" / "site.ts")
    check(f'version: "{NPM}"' in site, "website SITE.version must be 1.0.0-rc.1")
    check(f'pythonVersion: "{PY}"' in site, "website SITE.pythonVersion must be 1.0.0rc1")
    check(f'tsVersion: "{NPM}"' in site, "website SITE.tsVersion must be 1.0.0-rc.1")
    check("statusLabel: \"Release candidate\"" in site, "website must label Release candidate, not stable v1.0")
    cli = read(ROOT / "apps" / "cli" / "src" / "main.rs")
    check("CARGO_PKG_VERSION" in cli, "CLI user-agent must use CARGO_PKG_VERSION")
    check("0.1.0-alpha" not in cli, "CLI must not hardcode 0.1.0-alpha")
    sqlx = tomllib.loads(read(ROOT / "Cargo.toml"))["workspace"]["dependencies"]["sqlx"]
    check(str(sqlx.get("version", "")).startswith("0.9"), "workspace sqlx must be 0.9.x (drops unused 0.8 mysql/sqlite lockfile crates)")
    overrides = json.loads(read(ROOT / "package.json")).get("overrides", {})
    check(overrides.get("dompurify") == "3.4.17", "root package.json must override DOMPurify to 3.4.17 (GHSA-c6gr-qvv4-5v3f)")
    check(overrides.get("postcss") == "8.5.32", "root package.json must override PostCSS to 8.5.32")
    check(overrides.get("hono") == "4.13.16", "root package.json must override hono to 4.13.16")
    check(overrides.get("@hono/node-server") == "2.1.6", "root package.json must override @hono/node-server to 2.1.6")
    if errors:
        print("assert_rc_versions failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"versions ok: cargo/npm={CARGO} python={PY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
