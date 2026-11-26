# Google Search Console and Bing Webmaster Tools

These steps apply to the Astro site on GitHub Pages. Public native archives are the stable release [`v1.0.0`](https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0). `v1.0.0-rc.1` and `v1.0.0-rc.2` remain published. Do not treat a release tag as Search Console setup or as a Pages deploy.

Do **not** promise indexing speed or rankings. This document is setup only.

Official site (Astro on GitHub Pages):

`https://goshikavs.github.io/goshikq-agent-framework/`

A custom domain is **not** authorized here. Do not change DNS without a separate owner decision.

## Preconditions (already true after PR #27)

1. `main` includes the Astro site. `.github/workflows/docs.yml` deploys to the `github-pages` environment.
2. `https://goshikavs.github.io/goshikq-agent-framework/` returns HTTP 200 for `/`, `/download/`, `/docs/`, `/studio/`, `/robots.txt`, and `/sitemap-index.xml`.
3. HTML contains `<link rel="canonical" …>` under that host and **no** `noindex`.
4. `robots.txt` contains `Allow: /` and a `Sitemap:` line pointing at the deployed sitemap.

Local preview is not Search Console. Google/Bing verification tokens are still owner-only. This repository does **not** invent a `google-site-verification` value.

## Why HTML-file verification 404s

GitHub Pages publishes `apps/website/dist` at `https://goshikavs.github.io/goshikq-agent-framework/`. Google’s HTML-file method requests:

`https://goshikavs.github.io/goshikq-agent-framework/<googleNNNN.html>`

A file at the repository root, or at `https://goshikavs.github.io/<googleNNNN.html>` (no repo path), is not in the Pages artifact. Prefer the **HTML tag** method below. If you still use the HTML file, put Google’s exact file in `apps/website/public/` so Astro copies it to that URL.

## Google Search Console

1. Open https://search.google.com/search-console
2. Add property → **URL prefix** → `https://goshikavs.github.io/goshikq-agent-framework/`
3. Choose **HTML tag**. Copy the `content` value from Google’s meta tag. Do not invent a token.
4. Repo **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `GOOGLE_SITE_VERIFICATION`
   - Value: that exact `content` string (no quotes, no `meta` markup)
5. Merge this change to `main` (or run **Docs** → `workflow_dispatch` after the secret exists). `.github/workflows/docs.yml` passes the secret into `PUBLIC_GOOGLE_SITE_VERIFICATION`, which `apps/website/src/layouts/Marketing.astro` writes into the homepage `<head>`.
6. View source on https://goshikavs.github.io/goshikq-agent-framework/ and confirm `<meta name="google-site-verification" content="…">` matches Google’s value.
7. Click **Verify** in Search Console. Do not claim verification until Google says it succeeded.
8. After Google confirms ownership: Sitemaps → add `https://goshikavs.github.io/goshikq-agent-framework/sitemap-index.xml`
9. URL Inspection → test `https://goshikavs.github.io/goshikq-agent-framework/` and `/download/`
10. Do not request indexing of unpublished or `noindex` URLs

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

- Creating the `GOOGLE_SITE_VERIFICATION` Actions secret with Google’s exact HTML-tag token
- Clicking **Verify** after the live homepage includes that meta tag
- Submitting `sitemap-index.xml` and requesting indexing
- Any custom domain or DNS
