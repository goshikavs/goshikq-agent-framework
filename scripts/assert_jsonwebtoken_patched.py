#!/usr/bin/env python3
"""Fail CI if Cargo.lock still has jsonwebtoken older than the GHSA-h395 patch.

GHSA-h395-gr6q-cpjc / CVE-2026-25537 is patched in jsonwebtoken 10.3.0.
cargo-audit uses rustsec and may not list every GitHub advisory. This gate
reads the lockfile the compiler actually uses.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "Cargo.lock"
MINIMUM = (10, 3, 0)


def parse_version(text: str) -> tuple[int, int, int]:
    parts = text.split(".")
    nums = []
    for part in parts[:3]:
        m = re.match(r"^(\d+)", part)
        if not m:
            raise ValueError(f"unparseable version component: {part!r}")
        nums.append(int(m.group(1)))
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def lockfile_jsonwebtoken_versions(text: str) -> list[str]:
    versions: list[str] = []
    blocks = text.split("[[package]]")
    for block in blocks:
        name = re.search(r'(?m)^name = "([^"]+)"', block)
        ver = re.search(r'(?m)^version = "([^"]+)"', block)
        if name and name.group(1) == "jsonwebtoken" and ver:
            versions.append(ver.group(1))
    return versions


def main() -> int:
    text = LOCK.read_text(encoding="utf-8")
    versions = lockfile_jsonwebtoken_versions(text)
    if not versions:
        print("assert_jsonwebtoken_patched: jsonwebtoken missing from Cargo.lock", file=sys.stderr)
        return 1
    failed = False
    for ver in versions:
        parsed = parse_version(ver)
        print(f"Cargo.lock jsonwebtoken {ver}")
        if parsed < MINIMUM:
            print(
                f"assert_jsonwebtoken_patched: {ver} is older than 10.3.0 "
                "(GHSA-h395-gr6q-cpjc / CVE-2026-25537)",
                file=sys.stderr,
            )
            failed = True
    if failed:
        return 1
    print("jsonwebtoken lockfile versions satisfy >= 10.3.0 (GHSA-h395-gr6q-cpjc)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
