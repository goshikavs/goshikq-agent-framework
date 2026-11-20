# Changelog

## v1.0.0-rc.1 — GitHub prerelease (2026-11-19)

GitHub prerelease: https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0-rc.1  
Tag target: `1f4d35dd6b73801ede2ec1e64ad906645c4d7a60`. Not stable v1.0. Not on PyPI, npm, or crates.io.

### Added

- `.github/workflows/release-candidate.yml`: native `--release` archives, packaged-binary smoke, SHA256SUMS, SPDX SBOM, isolated SDK packs
- `scripts/package_release.py`, `scripts/smoke_packaged_runtime.py`, version/sqlx graph gates
- Native GitHub Actions matrix: Linux x64/ARM64, Windows x64, macOS Intel/ARM64; Windows ARM64 experimental
- rustfmt + clippy job; Python 3.11–3.13 unit matrix; linux/arm64 Docker smoke job
- Sandbox examples: bank-account-update, travel-booking, enterprise-access
- Adversarial verification, mixed Python/TypeScript runtime, and migration inventory tests
- `docs/release/v1.0-*` execution, audit, gates, platform, artifact, and owner-publish reports

### Changed

- Workspace sqlx 0.8 → 0.9 (PostgreSQL features only; `rsa` / Marvin dropped from `Cargo.lock`)
- bun overrides: DOMPurify 3.4.17 (GHSA-c6gr-qvv4-5v3f), PostCSS 8.5.32, Hono 4.13.16, `@hono/node-server` 2.1.6
- `bun audit` is a required CI gate
- cargo-audit ignore retained only for unused sqlx-sqlite `libsqlite3-sys` (RUSTSEC-2026-0459), with `cargo tree` proof


## Unreleased — GitHub baseline / CI (not a v1.0 tag)

Private repository connected. Required GitHub Actions jobs are green on `main` at `e7d5b70`. Packages and public releases are still not published.

### Fixed

- GitHub Actions Bun pin 1.4.4 so workspace `bun.lock` (`lockfileVersion` 2) is honored
- Studio workflow editor `Node[]` typing against `@xyflow/react` `Position`
- Python `ruff` E501 on existing SDK lines (other selected rules still enforced)
- Runtime Docker image `rustc` 1.98 so `postgresql_embedded` 0.20.4 / `sqlx` 0.9 compile
- `cargo audit` ignore for `RUSTSEC-2023-0071` (`rsa` via unused `sqlx-mysql`; no upstream fix)
- OpenAPI export no longer parses `DATABASE_URL=embedded`
- Compose `studio` profile includes `runtime` so `depends_on` resolves
- Python `Verification`/`Effect`/`Risk` use `StrEnum` (ruff UP042)
- Example pytest jobs run per directory so `main` imports do not collide
- Example tests load sibling `main.py` by unique module name so a combined pytest collection cannot import the wrong `main`
- Pin TypeScript `zod` to 4.6.7 (GHSA-mrhx-c7xc-m3w5) and point Dependabot npm at the workspace `bun.lock`

## Unreleased — v0.9.1 (not published)

Release-gate closure on top of v0.9. Not a v1.0 tag. Docker smoke and GitHub Actions have not run on this authoring host.

### Added

- RS256 JWKS OIDC interoperability tests (issuer, audience, expiry, signature, key rotation, alg restrictions, cross-tenant)
- Native runtime OTLP/HTTP JSON export (`GOSHIKQ_OTEL_EXPORTER_OTLP_ENDPOINT`) with redaction and sampling; inbound ingest unchanged
- Owner-only `POST /api/v1/admin/retention/purge` (dry-run default; skips active parents)
- Studio Dockerfile and compose `studio` profile
- Isolated Python wheel / TypeScript tarball install tests outside the repository
- GitHub Actions jobs for rust, SDKs, Studio, Playwright, Postgres integration, docker-smoke, secret scan, audits (not executed)
- `docs/milestones/v0.9.1-report.md`, `docs/release/v1.0-readiness.md`, `docs/release/release-checklist.md`, platform matrix

### Changed

- Unknown JWT `kid` forces a JWKS refresh (key rotation)
- HMAC tokens rejected unless loopback `GOSHIKQ_OIDC_ALLOW_TEST_HMAC`
- Playwright inspector security test seeds via `pw-missing-telemetry` instead of skipping

## Unreleased — v0.9 (not published)

Production hardening on top of v0.1–v0.8. Packages, images, and GitHub releases are **not** published in this cycle.

### Added

- `GOSHIKQ_AUTH_MODE=oidc` with JWKS/issuer/audience validation; loopback HMAC test mode
- Project membership, RBAC, API key rotate/revoke/expiry, security events
- Registered workflow TOOL dispatch through the worker protocol
- Spawned AGENT nodes fail `WORKER_UNAVAILABLE` instead of succeeding without a worker
- `/api/v1/runtime/metrics`, JSON logs, pool/lease/recovery counters
- Tenant isolation and reliability tests
- Docker files (image smoke untested without Docker Desktop on the authoring host)

### Security

- Server-side permission checks on sensitive routes
- Worker poll verifies project ownership before using an in-memory handle
- A2A message size cap; untrusted verification claims remain ignored
