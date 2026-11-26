#!/usr/bin/env python3
"""Assemble a native Goshikq release-candidate archive from cargo --release binaries."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LICENSE = ROOT / "LICENSE"

INSTALL_TEMPLATE = """# Goshikq {version} ({platform})

This archive is version **{version}**. It is not a GitHub Release until the owner publishes that tag.

- Source commit: `{commit}`
- Built with `cargo build --release` (not debug)
- GitHub Release publication requires separate owner approval

## Contents

- `{server}` — Goshikq runtime
- `{cli}` — Goshikq CLI
- `LICENSE` — Apache-2.0
- `NOTICE` — third-party attribution pointer
- `INSTALL.md` — this file

SDKs are not inside this archive. Install Python `goshikq-ai` and TypeScript `@goshikq/sdk` from a built wheel/tarball or from source. They are not on PyPI or npm until the owner publishes them.

## Start (development)

Embedded PostgreSQL (`DATABASE_URL=embedded`) downloads Theseus binaries from GitHub on first run. Production must set a real `DATABASE_URL` and must not use `GOSHIKQ_AUTH_MODE=none`.

Unix:

```sh
chmod +x {server} {cli}
export DATABASE_URL=embedded
export GOSHIKQ_AUTH_MODE=none
./{server}
```

Windows (cmd):

```bat
set DATABASE_URL=embedded
set GOSHIKQ_AUTH_MODE=none
{server}
```

Health: `http://127.0.0.1:7400/health` and `/ready`.

```sh
./{cli} --version
./{cli} doctor
```

## Do not ship this tree

This archive must not contain `.env`, database credentials, Studio screenshots of private data, or `target/` debug binaries.
"""

NOTICE_TEMPLATE = """Goshikq {version}
Copyright Venkatesh Goshika

Licensed under the Apache License, Version 2.0. See LICENSE.

This product includes third-party software. Dependency versions are recorded in
the repository lockfiles (Cargo.lock, bun.lock, sdk/python/pyproject.toml) at
commit {commit}. A SPDX SBOM is produced by the release-candidate GitHub Actions
workflow when that workflow runs.

jsonwebtoken is used for RS256 JWT *signature verification*, not RSA PKCS#1 v1.5
decryption. The runtime talks to PostgreSQL only.
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_bin(release_dir: Path, name: str) -> Path:
    exe = release_dir / f"{name}.exe"
    plain = release_dir / name
    if exe.exists():
        return exe
    if plain.exists():
        return plain
    raise FileNotFoundError(f"missing {name} in {release_dir}")


def is_windows(platform: str) -> bool:
    return platform.startswith("windows")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--platform", required=True, help="linux-amd64, windows-amd64, ...")
    p.add_argument("--version", default="1.0.0")
    p.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "unknown"))
    p.add_argument("--release-dir", default="target/release")
    p.add_argument("--out-dir", default="dist")
    p.add_argument("--experimental", action="store_true")
    args = p.parse_args()

    release_dir = Path(args.release_dir)
    server = find_bin(release_dir, "goshikq-server")
    cli = find_bin(release_dir, "goshikq")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    staging = out_dir / f"staging-{args.platform}"
    if staging.exists():
        import shutil

        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    server_name = server.name
    cli_name = cli.name
    (staging / server_name).write_bytes(server.read_bytes())
    (staging / cli_name).write_bytes(cli.read_bytes())
    if not is_windows(args.platform):
        for name in (server_name, cli_name):
            path = staging / name
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (staging / "LICENSE").write_bytes(LICENSE.read_bytes())
    (staging / "NOTICE").write_text(
        NOTICE_TEMPLATE.format(version=args.version, commit=args.commit),
        encoding="utf-8",
    )
    (staging / "INSTALL.md").write_text(
        INSTALL_TEMPLATE.format(
            version=args.version,
            platform=args.platform,
            commit=args.commit,
            server=server_name,
            cli=cli_name,
        ),
        encoding="utf-8",
    )
    (staging / "COMMIT.txt").write_text(f"{args.commit}\n{args.platform}\n{args.version}\n", encoding="utf-8")
    if args.experimental:
        (staging / "EXPERIMENTAL.txt").write_text(
            "Windows ARM64 is experimental. Not a v1.0 required platform.\n",
            encoding="utf-8",
        )

    forbidden = [p for p in staging.rglob("*") if p.suffix in {".env", ".pem", ".key"} or p.name == ".env"]
    if forbidden:
        raise SystemExit(f"refusing to package secrets: {forbidden}")

    base = f"goshikq-{args.version}-{args.platform}"
    if is_windows(args.platform):
        archive = out_dir / f"{base}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(staging.rglob("*")):
                if f.is_file():
                    zf.write(f, arcname=f"{base}/{f.relative_to(staging).as_posix()}")
    else:
        archive = out_dir / f"{base}.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(staging, arcname=base)

    digest = sha256_file(archive)
    (out_dir / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
