# Packaging

Native GitHub **prerelease** `v1.0.0-rc.2`: https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0-rc.2. Nothing is published to PyPI, npm, or crates.io. Stable `v1.0.0` is a separate approval. `v1.0.0-rc.1` remains published and is superseded due to `jsonwebtoken` 9.3.1.

## Python (`sdk/python`)

- `pyproject.toml` with hatchling, version `1.0.0rc2` (PEP 440; unpublished). Public GitHub archives are `v1.0.0-rc.2`.
- Optional extras: `openai`, `anthropic`, `dev`
- Isolated install (temp venv **outside** the repo): `python -m pytest tests/packaging/test_isolated_install.py`
- Local smoke: `python -m build` then `pip install dist/*.whl` and `python -c "import goshikq_ai"`

## TypeScript (`sdk/typescript`)

- ESM package `@goshikq/sdk` shipping TypeScript sources for Bun
- `engines.node: >=20`; Node consumers should use Bun or a TypeScript loader. A compiled `dist/` emit is not the supported path in this alpha
- Local smoke: `bun pm pack` then `bun add ./goshikq-sdk-1.0.0-rc.2.tgz`

## Rust runtime

- Workspace version `1.0.0-rc.2` (Cargo/SemVer prerelease; GitHub native archives published, crates.io unpublished)
- `GET /health` reports `version`
- Native platforms: see `docs/release/v1.0-supported-platforms.md`. Release-profile archives are built by `.github/workflows/release-candidate.yml`.

## Studio

- `bun run build` in `apps/studio` for a production Next.js build
- Runtime URL: `GOSHIKQ_STUDIO_RUNTIME_URL` or `GOSHIKQ_RUNTIME_URL` (default `http://127.0.0.1:7400`)
- Migrations are additive (`0001`–`0006`); existing databases migrate on server start
