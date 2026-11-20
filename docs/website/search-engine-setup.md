# Search engine setup (website)

A sitemap does not force indexing. This page is for the **Astro website**, not a claim that Google has indexed anything.

Intended public host: `https://goshikavs.github.io/goshikq-agent-framework/` (Astro + Starlight via `.github/workflows/docs.yml`). Until `release/v1.0-hardening` is merged to `main` and Pages deploys, that URL may still serve the older VitePress artifact or 404. See [search-console-setup.md](search-console-setup.md) for Google/Bing steps.

## After a public origin exists

1. Rebuild with `PUBLIC_SITE_URL=https://goshikavs.github.io` and `PUBLIC_BASE_PATH=/goshikq-agent-framework/` (origin only — putting the repo path in `PUBLIC_SITE_URL` drops `/goshikq-agent-framework/` from canonicals).
2. Confirm `https://goshikavs.github.io/goshikq-agent-framework/sitemap-index.xml` and `/goshikq-agent-framework/robots.txt` return 200.
3. Google Search Console → URL prefix property for that origin.
4. HTML-tag verification: put `google-site-verification` in `apps/website/astro.config.mjs` `head` (or a file in `apps/website/public/`). Do not commit a token until Search Console issues one.
5. Sitemap submission: paste `https://<origin>/sitemap-index.xml`.
6. URL Inspection → request indexing for `/` and `/docs/`. Requests are not a ranking guarantee.
7. Bing Webmaster Tools → import from Search Console or add the same prefix and sitemap.

## GitHub repository

Keep the repository URL-prefix property as documented in [guides/search-console.md](../guides/search-console.md).

## Recommended GitHub About (manual)

GitHub repository settings are not changed by this branch unless the owner updates them.

- Description: `Open-source AI agent framework with a Rust runtime for durable execution, multi-agent orchestration, and verified outcomes.`
- Website: `https://goshikavs.github.io/goshikq-agent-framework/` (already set on the GitHub repo). Custom domain remains owner-only.
- Topics: `ai-agents`, `rust`, `python`, `typescript`, `durable-execution`, `multi-agent`, `open-source`

Do not rename the repository or change visibility.
