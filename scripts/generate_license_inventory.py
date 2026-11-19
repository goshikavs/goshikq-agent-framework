#!/usr/bin/env python3
"""Write a dependency/license inventory from cargo metadata + npm/python manifests."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    out = Path("dist/sbom")
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads(subprocess.check_output(["cargo", "metadata", "--format-version", "1"]))
    rust = []
    for pkg in sorted(meta["packages"], key=lambda p: (p["name"], p["version"])):
        if pkg["name"].startswith("goshikq"):
            source = "workspace"
        else:
            source = pkg.get("source") or "path"
        rust.append(
            {
                "name": pkg["name"],
                "version": pkg["version"],
                "license": pkg.get("license"),
                "source": source,
            }
        )
    py = tomllib.loads((ROOT / "sdk" / "python" / "pyproject.toml").read_text(encoding="utf-8"))
    npm = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    ts = json.loads((ROOT / "sdk" / "typescript" / "package.json").read_text(encoding="utf-8"))
    studio = json.loads((ROOT / "apps" / "studio" / "package.json").read_text(encoding="utf-8"))
    inventory = {
        "product": "goshikq",
        "version": next(p["version"] for p in meta["packages"] if p["name"] == "goshikq-server"),
        "rust": rust,
        "python_package": {"name": py["project"]["name"], "version": py["project"]["version"], "license": "Apache-2.0"},
        "python_direct_deps": py["project"]["dependencies"],
        "npm_workspace": {"name": npm["name"], "version": npm["version"], "overrides": npm.get("overrides", {})},
        "typescript_sdk": {"name": ts["name"], "version": ts["version"], "dependencies": ts.get("dependencies", {})},
        "studio_direct_deps": studio.get("dependencies", {}),
        "notes": "This inventory is not a substitute for the SPDX SBOM. Optional sqlx mysql/sqlite crates may appear in Cargo.lock without being reachable from goshikq-server.",
    }
    path = out / "license-inventory.json"
    path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    md = out / "license-inventory.md"
    lines = [
        "# Goshikq dependency/license inventory",
        "",
        f"Runtime crate version: `{inventory['version']}`",
        "",
        "## Python",
        f"- `{inventory['python_package']['name']}` `{inventory['python_package']['version']}` Apache-2.0",
        "",
        "## TypeScript",
        f"- `{inventory['typescript_sdk']['name']}` `{inventory['typescript_sdk']['version']}`",
        "",
        "## Rust crates (lockfile)",
        "",
        "| name | version | license |",
        "| --- | --- | --- |",
    ]
    for row in rust:
        lic = (row["license"] or "").replace("|", "/")
        lines.append(f"| `{row['name']}` | {row['version']} | {lic} |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
