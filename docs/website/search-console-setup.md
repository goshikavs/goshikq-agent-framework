# Google Search Console and Bing Webmaster Tools

These steps apply after the Astro site is deployed to GitHub Pages. Public native archives are already [`v1.0.0-rc.2`](https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0-rc.2). Do not treat that tag as Search Console setup or as a Pages deploy.

Do **not** promise indexing speed or rankings. This document is setup only.

Official site (Astro on GitHub Pages):

`https://goshikavs.github.io/goshikq-agent-framework/`

A custom domain is **not** authorized here. Do not change DNS without a separate owner decision.

## Preconditions (already true after PR #27)

1. `main` includes the Astro site. `.github/workflows/docs.yml` deploys to the `github-pages` environment.
2. `https://goshikavs.github.io/goshikq-agent-framework/` returns HTTP 200 for `/`, `/download/`, `/docs/`, `/studio/`, `/robots.txt`, and `/sitemap-index.xml`.
3. HTML contains `<link rel="canonical" …>` under that host and **no** `noindex`.
4. `robots.txt` contains `Allow: /` and a `Sitemap:` line pointing at the deployed sitemap.

Local preview is not Search Console. Google/Bing verification tokens are still owner-only.

## Google Search Console

1. Open https://search.google.com/search-console
2. Add property → **URL prefix** → `https://goshikavs.github.io/goshikq-agent-framework/`
3. Verify with **HTML file** or **Google Analytics** only if those are already owned. Preferred for this repo: **DNS** is unavailable without a custom domain. Use **HTML tag** in `apps/website/src/layouts/Marketing.astro` **only after** the owner supplies the exact verification token. Do not invent a token.
4. After verification, Sitemaps → add `https://goshikavs.github.io/goshikq-agent-framework/sitemap-index.xml`
5. URL Inspection → test `https://goshikavs.github.io/goshikq-agent-framework/` and `/download/`
6. Do not request indexing of unpublished or `noindex` URLs

GitHub org verification (optional): Search Console also supports a **Domain** property on `github.io`, which Google verifies through GitHub’s documented process. That is an owner Google-account action.

## Bing Webmaster Tools

1. Open https://www.bing.com/webmasters
2. Add site `https://goshikavs.github.io/goshikq-agent-framework/`
3. Import from Search Console if already verified, or upload the Bing XML/HTML verification file the UI provides — again, only with the real token.
4. Submit the same sitemap URL as Google.
5. Use Bing’s URL inspection on the live Pages URLs.

## What this RC already prepares

- Static HTML (Astro) so primary copy is visible without JavaScript.
- `robots.txt` allows crawling.
- Canonical URLs derived from `PUBLIC_SITE_URL` + `PUBLIC_BASE_PATH`.
- README points at the GitHub Pages URL.
- Homepage / About website field: set the GitHub repo **Website** to `https://goshikavs.github.io/goshikq-agent-framework/` (owner/API).

## Canonical and URL inspection (after deploy is HTTP 200)

1. Open the live homepage and confirm `<link rel="canonical" href="https://goshikavs.github.io/goshikq-agent-framework/">`.
2. Confirm `/docs/`, `/quickstart/`, `/download/`, and `/studio/` canonicals keep `/goshikq-agent-framework/` and do not use `localhost`.
3. Fetch `https://goshikavs.github.io/goshikq-agent-framework/robots.txt` — `Allow: /` and `Sitemap: https://goshikavs.github.io/goshikq-agent-framework/sitemap-index.xml`.
4. Fetch the sitemap. Every `<loc>` must be under that prefix.
5. Google Search Console → URL Inspection → live test for `/` and `/docs/`. Request indexing only after the live test is valid. A request is not a ranking guarantee.
6. Repeat URL inspection in Bing Webmaster Tools.

## What remains owner-only

- Google/Bing account verification tokens (do not invent a `google-site-verification` value)
- Submitting `sitemap-index.xml` and requesting indexing
- Any custom domain or DNS
