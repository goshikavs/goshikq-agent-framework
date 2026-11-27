# Installation

GitHub Release [`v1.0.0`](https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0) publishes the stable native archives. `v1.0.0-rc.1` is superseded because it shipped `jsonwebtoken` 9.3.1. `v1.0.0-rc.2` remains published. Python and TypeScript SDKs are not on PyPI or npm. Windows ARM64 is experimental.

## Published runtime

These commands download a pinned installer, check its SHA256, and install the v1.0.0 archives. They do not clone the repository and they do not install a language SDK. A clone is not required. The manual alternative is the release archive plus `SHA256SUMS`.

```bash
curl -fsSL -o goshikq-install.sh https://raw.githubusercontent.com/goshikavs/goshikq-agent-framework/b830e15efa2f7bd05af0769739c6cab6feb40d97/scripts/install.sh
echo "4630175aa8868d58b634df1043abdd0fae425d78c93326401d41e5ed5a752590  goshikq-install.sh" | sha256sum -c -
sh goshikq-install.sh --version v1.0.0
```

macOS uses `shasum -a 256 -c -` instead of `sha256sum -c -`. Windows saves `scripts/install.ps1` from the same commit (`75fdf00099a9a464fff1e0d54495037cff2d1dc6046a035ad9df2b5ea5f1822f`) and runs `powershell -ExecutionPolicy Bypass -File .\goshikq-install.ps1 -Version v1.0.0`.

Follow the printed PATH line. `goshikq --version` prints `goshikq 1.0.0`. Then start `goshikq-server` with `DATABASE_URL=embedded`, `GOSHIKQ_AUTH_MODE=none`, and `GOSHIKQ_BIND=127.0.0.1:7400`. `curl -fsS http://127.0.0.1:7400/health` includes `"version":"1.0.0"`. The first embedded PostgreSQL start downloads a database and needs network access. `GOSHIKQ_AUTH_MODE=none` is only for this loopback process.

The installer writes `hello_agent.py` beside the binaries. Run the Python command it prints. Expected text includes `verification:  VERIFIED` and `evidence:      greetings-memory@1`.

`pip install goshikq-ai` does not work yet. `npm install @goshikq/sdk` does not work yet. After a real package install, the standalone files are `examples/quickstart/sdk_hello.py` and `examples/quickstart/hello.mjs` (`node hello.mjs`, Node.js 20+, ESM only). Registry commands stay off until [the publication switch](../release/v1.0.1-publication-switch.md).

From-source install below was tested on Windows x64 (MSVC) with PostgreSQL on `127.0.0.1:55432`.

## Runtime

```text
# PostgreSQL
# DATABASE_URL=postgres://postgres:goshikq@127.0.0.1:55432/goshikq

scripts/with-msvc.ps1 cargo +stable-x86_64-pc-windows-msvc build -p goshikq-server
$env:DATABASE_URL="postgres://postgres:goshikq@127.0.0.1:55432/goshikq"
$env:GOSHIKQ_BIND="127.0.0.1:7400"
$env:GOSHIKQ_AUTH_MODE="none"
.\target\debug\goshikq-server.exe
```

On ARM64 Windows, compile the x86_64 target as above. Native ARM64 `link.exe` is not used.

## Studio

```text
cd apps/studio
bun install
bun run dev
# http://127.0.0.1:3000
```

## Python

What you install: `goshikq-ai`, the SDK. It is not the runtime.

```text
python -m pip install -e sdk/python
```

That command is the verified install. `pip install goshikq-ai` does not work yet. The prepared package version is 1.0.1. CPython 3.11–3.14. Start `goshikq-server` first. `Runtime.run_sync` prints a status and a verification status. `VERIFIED` requires a goal predicate, not a successful tool return.

Troubleshooting: an import error means the package was not installed from this clone. A connection error means `goshikq-server` is not reachable at `GOSHIKQ_RUNTIME_URL` (default `http://127.0.0.1:7400`). `COMPLETED` without `VERIFIED` means the goal predicate did not accept the snapshot.

## TypeScript / JavaScript

What you install: `@goshikq/sdk`. Node.js 20+ or Bun. ESM only.

```text
cd sdk/typescript
bun install
bun run build
```

`npm install @goshikq/sdk` does not work yet. The prepared package version is 1.0.1. A clean consumer imports the built JavaScript:

```javascript
import { Agent, Goal, Runtime } from "@goshikq/sdk";
```

CommonJS `require()` is not supported.

Troubleshooting: `npm install @goshikq/sdk` returns 404 until the package is published. `Cannot find module` after a source checkout means `bun run build` has not produced `dist/`. `require()` fails because the package is ESM only.

## Rust / CLI

What you install: the v1.0.0 GitHub Release binaries `goshikq` and `goshikq-server`.

```text
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Version v1.0.0
sh scripts/install.sh --version v1.0.0
```

crates.io publication is deferred. Workspace crates set `publish = false`. They use path dependencies and are not a stable external Rust library.

Troubleshooting: a SHA256 mismatch means the download is discarded; do not bypass the check. Windows ARM64 prints an experimental warning and is not a supported v1.0 platform. `install.sh` is for macOS and Linux. On this Windows host it is not the installer that was executed.

Do not publish PyPI, npm, or crates.io packages without owner authorization.

## Three-minute offline quickstart

1. Start Postgres and `goshikq-server` as above.
2. `python examples/hello-agent/main.py`
3. Open Studio Executions and confirm `VERIFIED`.
