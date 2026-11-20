#!/usr/bin/env python3
"""Fail if Goshikq runtime crates link unused sqlx MySQL/SQLite backends.

sqlx records optional mysql/sqlite crates in Cargo.lock even with those
features disabled. `cargo tree -p goshikq-server -i libsqlite3-sys` is the
runtime-link proof cargo-audit cannot make by itself.
"""

from __future__ import annotations

import subprocess
import sys

PACKAGES = ("goshikq-server", "goshikq-cli", "goshikq-storage", "goshikq-runtime")
FORBIDDEN = ("sqlx-mysql", "sqlx-sqlite", "libsqlite3-sys")


def tree_has(package: str, crate: str) -> tuple[bool, str]:
    proc = subprocess.run(
        ["cargo", "tree", "-p", package, "--target", "all", "-i", crate],
        capture_output=True,
        text=True,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    lower = text.lower()
    # Unused lockfile crates: cargo tree either warns "nothing to print" or
    # errors "did not match any packages" for a package that does not depend
    # on sqlx at all (goshikq-cli).
    unused = "nothing to print" in lower or "did not match any packages" in lower
    return (not unused, text)


def main() -> int:
    hits: list[str] = []
    for package in PACKAGES:
        for crate in FORBIDDEN:
            present, text = tree_has(package, crate)
            if present:
                hits.append(f"{package} -> {crate}\n{text}")
    if hits:
        print("Forbidden sqlx backends reachable from Goshikq runtime crates:", file=sys.stderr)
        for h in hits:
            print(h, file=sys.stderr)
        return 1
    print("cargo tree --target all: sqlx-mysql / sqlx-sqlite / libsqlite3-sys not linked from")
    for p in PACKAGES:
        print(f"  - {p}")
    print("Cargo.lock may still list optional sqlx backends; that is why RUSTSEC-2026-0459 is ignored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
