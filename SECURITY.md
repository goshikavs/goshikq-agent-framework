# Security policy

Report vulnerabilities privately to the repository owner (GitHub: goshikavs). Do not open public issues with exploit details.

**Current supported stable version: v1.0.0.**

The latest public GitHub Release is stable `v1.0.0` (commit `83bc8e71edf46a20986f2380309e3d74d0ff3ab9`). Install that release. `v1.0.0-rc.1` and `v1.0.0-rc.2` are historical prereleases, not the recommended production versions. `v1.0.0-rc.1` is superseded because it shipped `jsonwebtoken` 9.3.1 (GHSA-h395-gr6q-cpjc / CVE-2026-25537). `v1.0.0-rc.2` remains published for history.

Verification records authoritative evidence at a point in time. A later external change does not rewrite a historical `VERIFIED` row. Exactly-once external side effects require an idempotency mechanism the external API honors. Prompt injection remains a residual risk. Windows ARM64 is experimental. `GOSHIKQ_AUTH_MODE=none` is for controlled local development only. Unmaintained-crate warnings remain for `chrono` (`RUSTSEC-2026-0543`), `paste` (`RUSTSEC-2024-0436`), and `pin-utils` (`RUSTSEC-2026-0441`). This project is not SOC 2, HIPAA, or PCI certified. Stable does not mean vulnerability-free or suitable for every regulated environment. Known residual risks are also listed in `docs/security/threat-model.md`.

`cargo audit` ignores `RUSTSEC-2026-0459` (`libsqlite3-sys` / C SQLite) because sqlx still records an unused SQLite backend in `Cargo.lock` while Goshikq enables only PostgreSQL. `cargo tree -p goshikq-server -i libsqlite3-sys` is empty; CI `scripts/assert_unused_sqlx_backends.py` fails if that graph changes. JWT verification uses `jsonwebtoken` **12.0.0** (`rust_crypto` + `use_pem`), patched for GHSA-h395-gr6q-cpjc / CVE-2026-25537. That path pulls `rsa` 0.10.0 for RS256/PS* signature verify only (Marvin patched; not PKCS#1 v1.5 decrypt). CI `scripts/assert_jsonwebtoken_patched.py` fails if `Cargo.lock` has jsonwebtoken older than 10.3.0. See `.cargo/audit.toml` and `docs/release/v1.0-security-review.md`.
