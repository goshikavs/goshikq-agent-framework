#!/usr/bin/env python3
"""Require stable package versions and the published v1.0.0 GitHub Release.

The published GitHub Release and website stay on stable `1.0.0`.
The workspace version is `1.0.1` so a future v1.0.1 release build reports that version.
Do not point public downloads at v1.0.1 until that release and its SHA256SUMS exist.
The Python and TypeScript SDKs prepared on this branch are `1.0.1` and are not on PyPI or npm.
Public downloads point at the stable GitHub Release. rc.1 and rc.2 stay published.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARGO = "1.0.1"
NPM = "1.0.0"
SDK_NPM = "1.0.1"
PY = "1.0.1"
PUBLIC_TAG = "v1.0.0"
PUBLIC_COMMIT = "83bc8e71edf46a20986f2380309e3d74d0ff3ab9"
PUBLIC_HASHES = {
    "goshikq-1.0.0-linux-amd64.tar.gz": "40ecd97e8bb1cab931b718b78be5bdc6cd26e6021a5ef1a1d275f4ca98cf1da9",
    "goshikq-1.0.0-linux-arm64.tar.gz": "4fe8798dde81b013edbae659b38865ce5bfbc8de3f761e15b0ffad58aed8fd49",
    "goshikq-1.0.0-macos-amd64.tar.gz": "6900504350b5ee9848729b3371a11af00d5a9733d68c39635322006c14be1f1c",
    "goshikq-1.0.0-macos-arm64.tar.gz": "459d2044f28d076f167ead1e58077027b207f1a4bda2112caf235614c52ecdc4",
    "goshikq-1.0.0-windows-amd64.zip": "526f0c19594112446a0d8c6d531216501a0ad81d55b26fb7e93ac80d228dd907",
    "goshikq-1.0.0-windows-arm64.zip": "4107cd9ef42a3f5fb51bd86a09ccba4cbde157c8f60c4858cb695f23123814ea",
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
    """Fail CI if public status or download URLs drift from published v1.0.0."""
    readme = read(ROOT / "README.md")
    check(
        f"releases/tag/{PUBLIC_TAG}" in readme,
        "README.md must link the published v1.0.0 GitHub Release",
    )
    check(
        "**Status:** GitHub **stable** release" in readme and PUBLIC_COMMIT in readme,
        "README.md status line must identify v1.0.0 and its source commit",
    )
    check("Latest Stable Release: v1.0.0" in readme, "README.md must lead with Latest Stable Release: v1.0.0")
    check("0.1.0-alpha" not in readme, "README.md must not advertise 0.1.0-alpha")
    check("Current release: v1.0.0-rc.2" not in readme, "README.md must not name rc.2 as the current release")
    check("There is **no** PyPI, npm, or crates.io package" in readme, "README.md must deny registry packages")
    check("Windows ARM64 is experimental" in readme, "README.md must keep Windows ARM64 experimental")
    check("superseded" in readme, "README.md must mark v1.0.0-rc.1 as superseded")
    check("jsonwebtoken" in readme, "README.md must explain the JWT reason rc.1 is superseded")
    check("v1.0.0-rc.2" in readme, "README.md must keep the published rc.2 release in history")
    check("pypi.org/project" not in readme, "README.md must not link a PyPI project page")

    security = read(ROOT / "SECURITY.md")
    check(
        "Current supported stable version: v1.0.0." in security,
        "SECURITY.md must name v1.0.0 as the supported stable version",
    )
    check(
        "latest public GitHub Release is stable `v1.0.0`" in security,
        "SECURITY.md must identify v1.0.0 as the latest public release",
    )
    check("historical prereleases" in security, "SECURITY.md must classify rc.1 and rc.2 as historical")
    check("superseded" in security, "SECURITY.md must mark v1.0.0-rc.1 as superseded")
    check("v1.0.0-rc.2" in security, "SECURITY.md must keep rc.2 published")

    site = read(ROOT / "apps" / "website" / "src" / "lib" / "site.ts")
    check('version: "1.0.0"' in site, "website SITE.version must be 1.0.0")
    check('pythonVersion: "1.0.0"' in site, "website SITE.pythonVersion must stay on published stable 1.0.0")
    check('tsVersion: "1.0.0"' in site, "website SITE.tsVersion must stay on published stable 1.0.0")
    check(
        f"releases/tag/{PUBLIC_TAG}" in site,
        "website public download links must point at published v1.0.0",
    )
    check(
        f"releases/download/{PUBLIC_TAG}" in site,
        "website asset base must be releases/download/v1.0.0",
    )
    check(
        "releases/download/v1.0.0-rc.1" not in site,
        "website must not keep v1.0.0-rc.1 as the public download target",
    )
    check(
        "releases/download/v1.0.0-rc.2" not in site,
        "website must not keep v1.0.0-rc.2 as the public download target",
    )
    check('statusLabel: "Stable"' in site, "website must label Stable")
    check("pypi.org/project" not in site, "website SITE must not claim a PyPI URL")

    download = read(ROOT / "apps" / "website" / "src" / "pages" / "download.astro")
    check(PUBLIC_COMMIT in download, "download page must name the v1.0.0 source commit")
    check("Windows ARM64 is experimental" in download, "download page must keep Windows ARM64 experimental")
    check("stable GitHub Release" in download, "download page must identify the stable release")
    check("superseded" in download, "download page must mark rc.1 as superseded")
    check("v1.0.0-rc.2" in download, "download page must say rc.2 remains published")
    check("releases/download/v1.0.0-rc.1" not in download, "download page must not attach rc.1 archive names as current assets")
    check("releases/download/v1.0.0-rc.2" not in download, "download page must not attach rc.2 archive names as current assets")
    for name, digest in PUBLIC_HASHES.items():
        check(name in download, f"download page must list {name}")
        check(digest in download, f"download page must list SHA256 for {name}")
    check("SHA256SUMS" in download, "download page must link SHA256SUMS")
    check("goshikq-1.0.0.spdx.json" in download, "download page must link the SPDX SBOM")
    check("license-inventory.md" in download, "download page must link the license inventory")
    check("artifact-manifest.json" in download, "download page must link the provenance manifest")

    install_ps1 = read(ROOT / "scripts" / "install.ps1")
    install_sh = read(ROOT / "scripts" / "install.sh")
    check('[string]$Version = "v1.0.0"' in install_ps1, "install.ps1 must default to v1.0.0")
    check('version="v1.0.0"' in install_sh, "install.sh must default to v1.0.0")
    check("v1.0.0-rc.2" not in install_ps1, "install.ps1 must not default to or document rc.2 as current")
    check("v1.0.0-rc.2" not in install_sh, "install.sh must not default to or document rc.2 as current")

    marketing = read(ROOT / "apps" / "website" / "src" / "layouts" / "Marketing.astro")
    check("softwareVersion: SITE.version" in marketing, "structured softwareVersion must follow SITE.version")

    getting = read(ROOT / "apps" / "website" / "src" / "content" / "docs" / "docs" / "getting-started.mdx")
    check(
        "releases/tag/v1.0.0" in getting,
        "getting-started must link published v1.0.0",
    )
    check("not on PyPI or npm" in getting, "getting-started must deny PyPI/npm packages")

    changelog = read(ROOT / "CHANGELOG.md")
    check("v1.0.0 — stable GitHub Release" in changelog, "CHANGELOG.md must record v1.0.0 as the stable release")
    check("v1.0.0-rc.2 — GitHub prerelease" in changelog, "CHANGELOG.md must record rc.2 as a GitHub prerelease")
    check(PUBLIC_COMMIT in changelog, "CHANGELOG.md must name the v1.0.0 commit")


def main() -> int:
    check(cargo_workspace_version() == CARGO, f"Cargo.toml workspace.package.version must be {CARGO}")
    check(pyproject_version() == PY, f"sdk/python/pyproject.toml version must be {PY} (PEP 440)")
    check(
        f'__version__ = "{PY}"' in read(ROOT / "sdk" / "python" / "src" / "goshikq_ai" / "_version.py"),
        f"Python _version.py must be {PY}",
    )
    npm_paths = [
        ROOT / "package.json",
        ROOT / "apps" / "studio" / "package.json",
        ROOT / "apps" / "website" / "package.json",
    ]
    for p in npm_paths:
        check(json_version(p) == NPM, f"{p.relative_to(ROOT)} version must be {NPM}")
    sdk_pkg = ROOT / "sdk" / "typescript" / "package.json"
    check(json_version(sdk_pkg) == SDK_NPM, f"sdk/typescript/package.json version must be {SDK_NPM}")
    ts_ver = read(ROOT / "sdk" / "typescript" / "src" / "version.ts")
    check(f'VERSION = "{SDK_NPM}"' in ts_ver, "sdk/typescript/src/version.ts must export 1.0.1")
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
    print(f"versions ok: cargo={CARGO} sdk_python={PY} sdk_typescript={SDK_NPM} public_download={PUBLIC_TAG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
