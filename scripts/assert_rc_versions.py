#!/usr/bin/env python3
"""Require consistent v1.0.0-rc.2 package versions across ecosystems.

Cargo/npm use SemVer prerelease `1.0.0-rc.2`.
Python uses PEP 440 `1.0.0rc2`.
Do not substitute one string into every ecosystem.
The published GitHub prerelease is v1.0.0-rc.2. Stable v1.0.0 is unpublished.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARGO = "1.0.0-rc.2"
NPM = "1.0.0-rc.2"
PY = "1.0.0rc2"
PUBLIC_TAG = "v1.0.0-rc.2"
PUBLIC_COMMIT = "07b0abd56bc84fc78532bc2ce8de2c14de9cf29b"
PUBLIC_HASHES = {
    "goshikq-1.0.0-rc.2-linux-amd64.tar.gz": "6919ccd70cad3febcf10555db028c4b751a14d6f44179979d8eb74c803ebdec8",
    "goshikq-1.0.0-rc.2-linux-arm64.tar.gz": "29a49afe0f57e2abf8d37460d2db1bfd7efafe03983f4b148fc3a08b06782b0f",
    "goshikq-1.0.0-rc.2-macos-amd64.tar.gz": "8d7b415a45fbc746b633c5e66f5c5cd61687d61fbcb4def43316db8156b7323e",
    "goshikq-1.0.0-rc.2-macos-arm64.tar.gz": "92cf0e3bda86d1649b7293a9fd5a0c2ef1389d38042409a1744087099553ddb5",
    "goshikq-1.0.0-rc.2-windows-amd64.zip": "8ee11215af1d9912c97d4928c7ef9fe960232de41685abbb4e7f3b0481414af0",
    "goshikq-1.0.0-rc.2-windows-arm64.zip": "7367c0b732474d369e463a45575ca30369652f5366f6d55a2a3c6806ea71a75c",
}

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


def check_release_status_and_download_links() -> None:
    """Fail CI if public status or download URLs drift from published rc.2."""
    readme = read(ROOT / "README.md")
    check(
        "releases/tag/v1.0.0-rc.2" in readme,
        "README.md must link the published v1.0.0-rc.2 GitHub prerelease",
    )
    check(
        "**Status:** GitHub **prerelease** [`v1.0.0-rc.2`]" in readme,
        "README.md status line must identify v1.0.0-rc.2 as the current public prerelease",
    )
    check(
        "not** stable v1.0" in readme or "not a published stable v1.0" in readme or "This is **not** stable v1.0" in readme,
        "README.md must still say this is not stable v1.0",
    )
    check("There is **no** PyPI, npm, or crates.io package" in readme, "README.md must deny registry packages")
    check("Windows ARM64 is experimental" in readme, "README.md must keep Windows ARM64 experimental")
    check("superseded" in readme, "README.md must mark v1.0.0-rc.1 as superseded")
    check("jsonwebtoken" in readme, "README.md must explain the JWT reason rc.1 is superseded")
    check("pypi.org/project" not in readme, "README.md must not link a PyPI project page")
    check("releases/download/v1.0.0/" not in readme, "README.md must not link a stable v1.0.0 archive")

    security = read(ROOT / "SECURITY.md")
    check(
        "latest public GitHub prerelease is `v1.0.0-rc.2`" in security,
        "SECURITY.md must identify v1.0.0-rc.2 as the latest public prerelease",
    )
    check("not a published stable v1.0" in security, "SECURITY.md must deny stable v1.0")
    check("superseded" in security, "SECURITY.md must mark v1.0.0-rc.1 as superseded")

    site = read(ROOT / "apps" / "website" / "src" / "lib" / "site.ts")
    check(f'version: "{NPM}"' in site, "website SITE.version must be 1.0.0-rc.2")
    check(f'pythonVersion: "{PY}"' in site, "website SITE.pythonVersion must be 1.0.0rc2")
    check(f'tsVersion: "{NPM}"' in site, "website SITE.tsVersion must be 1.0.0-rc.2")
    check(
        f"releases/tag/{PUBLIC_TAG}" in site,
        "website public download links must point at published v1.0.0-rc.2",
    )
    check(
        f"releases/download/{PUBLIC_TAG}" in site,
        "website asset base must be releases/download/v1.0.0-rc.2",
    )
    check(
        "releases/download/v1.0.0-rc.1" not in site,
        "website must not keep v1.0.0-rc.1 as the public download target",
    )
    check("releases/download/v1.0.0/" not in site, "website must not link unpublished stable v1.0.0 assets")
    check('statusLabel: "Release candidate"' in site, "website must label Release candidate, not stable v1.0")
    check("pypi.org/project" not in site, "website SITE must not claim a PyPI URL")

    download = read(ROOT / "apps" / "website" / "src" / "pages" / "download.astro")
    check(PUBLIC_COMMIT in download, "download page must name the rc.2 source commit")
    check("Windows ARM64 is experimental" in download, "download page must keep Windows ARM64 experimental")
    check("not stable v1.0" in download, "download page must deny stable v1.0")
    check("superseded" in download, "download page must mark rc.1 as superseded")
    check("releases/download/v1.0.0-rc.1" not in download, "download page must not attach rc.1 archive names as current assets")
    for name, digest in PUBLIC_HASHES.items():
        check(name in download, f"download page must list {name}")
        check(digest in download, f"download page must list SHA256 for {name}")

    getting = read(ROOT / "apps" / "website" / "src" / "content" / "docs" / "docs" / "getting-started.mdx")
    check(
        "releases/tag/v1.0.0-rc.2" in getting,
        "getting-started must link published v1.0.0-rc.2",
    )
    check("not stable v1.0" in getting, "getting-started must deny stable v1.0")
    check("not on PyPI or npm" in getting, "getting-started must deny PyPI/npm packages")

    changelog = read(ROOT / "CHANGELOG.md")
    check("v1.0.0-rc.2 — GitHub prerelease" in changelog, "CHANGELOG.md must record rc.2 as a GitHub prerelease")
    check("Not tagged. Not a GitHub Release." not in changelog.split("## v1.0.0-rc.1", 1)[0], "CHANGELOG rc.2 section must not still say unpublished")


def main() -> int:
    check(cargo_workspace_version() == CARGO, f"Cargo.toml workspace.package.version must be {CARGO}")
    check(pyproject_version() == PY, f"sdk/python/pyproject.toml version must be {PY} (PEP 440)")
    check(
        '__version__ = "1.0.0rc2"' in read(ROOT / "sdk" / "python" / "src" / "goshikq_ai" / "_version.py"),
        "Python _version.py must match PEP 440 1.0.0rc2",
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
    check(f'"{NPM}"' in ts_ver, "sdk/typescript/src/version.ts must export 1.0.0-rc.2")
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
    check_release_status_and_download_links()
    if errors:
        print("assert_rc_versions failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"versions ok: cargo/npm={CARGO} python={PY} public={PUBLIC_TAG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
