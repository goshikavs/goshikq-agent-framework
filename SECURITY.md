# Security policy

Report vulnerabilities privately to the repository owner (GitHub: goshikavs). Do not open public issues with exploit details.

This project is `1.0.0-rc.1` in tree and is **not a published stable v1.0**. Known residual risks are listed in `docs/security/threat-model.md`. Prompt injection is not solved. `GOSHIKQ_AUTH_MODE=none` is local development only.

`cargo audit` ignores `RUSTSEC-2026-0459` (`libsqlite3-sys` / C SQLite) because sqlx still records an unused SQLite backend in `Cargo.lock` while Goshikq enables only PostgreSQL. `cargo tree -p goshikq-server -i libsqlite3-sys` is empty; CI `scripts/assert_unused_sqlx_backends.py` fails if that graph changes. The `rsa` Marvin advisory (RUSTSEC-2023-0071) is gone from the lockfile after the sqlx 0.9 upgrade (JWT verification uses `jsonwebtoken`/`ring`, not RSA decrypt). See `.cargo/audit.toml` and `docs/release/v1.0-security-review.md`.
