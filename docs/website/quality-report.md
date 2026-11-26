# Website quality report

Public site: Astro + Starlight in `apps/website`. GitHub Pages deploy is `.github/workflows/docs.yml` on `main` (live after PR #27).

## Pages implemented

Marketing: `/`, `/features/`, `/quickstart/`, `/download/`, `/studio/`, `/architecture/`, `/examples/`, `/examples/refund-verification/`, `/examples/insurance-claims/`, `/community/`. `/changelog/` and `/roadmap/` redirect into docs.

Documentation: Starlight under `/docs/**` (installation, architecture, verification, evidence, recovery, multi-agent, workflows, Studio, integrations, security, operations, API, status, packaging, changelog, roadmap).

## Claims policy

- Tree package version `1.0.0` (Python `1.0.0`). Public GitHub Release is stable `v1.0.0`.
- No PyPI, npm, or crates.io packages. Native archives are the GitHub Release.
- No SOC 2 / HIPAA / PCI.
- Studio Tools/Goals/Evaluations/Regression/Benchmarks remain planned.
- Homepage verification demo is labeled as not a live runtime.

## Hosting

| Item | Plan | Notes |
| --- | --- | --- |
| Hosting | GitHub Pages | Static `apps/website/dist`. Deploy on `main` via `docs.yml` |
| Domain | Not purchased | `goshikavs.github.io/goshikq-agent-framework/` |
| Search | Pagefind static index | No Algolia |
| Analytics | None | Optional later |

## Test results (this branch)

| Check | Result |
| --- | --- |
| `bun run check` (`astro check`) | 0 errors, 0 warnings, 0 hints (27 files) |
| GitHub Pages base-path build | Pass — canonicals under `https://goshikavs.github.io/goshikq-agent-framework/` |
| Local `bun run build` | 47 HTML pages, Pagefind index, `sitemap-index.xml`, `robots.txt` |
| Playwright desktop 1440 + mobile 375 | 32 passed, 0 skipped |
| robots.txt | `Allow: /`, Sitemap to the Pages URL, no sitewide Disallow |
| Canonical / noindex | Marketing pages have `rel=canonical` and `index,follow` |
| Download honesty | Links are `v1.0.0` GitHub Release assets; SHA256SUMS GET 200 |
| Axiom chrome | Not present on homepage |
| Mobile overflow | Homepage kicker wrap, install `pre` wrap, architecture diagram contained |
| Lighthouse | Not a CI gate. DOMContentLoaded asserted under 20s in Playwright |
| Production Pages URL | Live after PR #27 — https://goshikavs.github.io/goshikq-agent-framework/ |

Visual review of local preview (`http://127.0.0.1:4321`): homepage, Studio gallery, Starlight `/docs/` sidebar/search. Studio thumbnails are captures from the running Next.js app, not placeholders.
