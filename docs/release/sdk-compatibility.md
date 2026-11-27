# SDK and runtime compatibility

This policy applies to the v1.0 line. It is not a promise that every future minor version keeps the same numbers across languages.

## Versions

| Piece | Identifier | Must match the runtime number? |
|---|---|---|
| Published GitHub Release | `v1.0.0` | Installers download this archive. Its CLI and `/health` report `1.0.0` |
| Workspace source for the next release build | `1.0.1` | `goshikq --version` and `/health` use `CARGO_PKG_VERSION`. A tag named v1.0.1 built from this source reports `1.0.1` |
| Protocol `SCHEMA_VERSION` | `1.0` | Unchanged. SDK 1.0.1 may talk to runtime 1.0.0 and 1.0.1 |
| Python `goshikq-ai` | `1.0.1` prepared, unpublished | No numerical match with the runtime is required |
| TypeScript `@goshikq/sdk` | `1.0.1` prepared, unpublished | Same as Python. ESM only. Node.js 20+ |
| Rust crates | workspace `1.0.1`, `publish = false` | Not a published library |

Patch releases of an SDK may add packaging, docs, and compatible bug fixes. They must not remove or rename public SDK exports that v1.0.0 examples use (`Agent`, `Goal`, `Runtime`, `tool` / `defineTool`, goal verification fields).

Minor runtime releases may add protocol fields. SDKs ignore unknown JSON fields. Removing or renaming a protocol field is a major change.

## Language runtimes

- Python: CPython 3.11, 3.12, 3.13, and 3.14 as declared in `sdk/python/pyproject.toml`. CI exercises that range. The clean-install gate on the maintainer machine used CPython 3.14.4.
- Node.js: 20 and newer for `@goshikq/sdk`. The clean consumer import was run with Node.js 24.15.0. CI packaging uses Node 22.
- Bun: 1.4.4 in CI. The SDK tests run under Bun. Bun is a supported way to execute the ESM build, not a second package format.
- Rust: the published CLI is the GitHub Release binary. Building from source uses the workspace `rust-version` (1.94) and, on this Windows ARM64 host, the x64 MSVC target.

## Deprecation

A deprecated SDK export stays for the rest of the 1.0 minor line and is named in `CHANGELOG.md` before removal. Removal waits for 2.0.

## What is not supported

Java, Kotlin, C#, and Go do not have SDKs. Calling the HTTP API from those languages is possible and is not a supported SDK. See `docs/release/v1.0.1-distribution.md`.
