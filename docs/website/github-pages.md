# GitHub Pages deployment (Astro website)

The public site is `apps/website` (Astro + Starlight), not a second VitePress tree.

Workflow: `.github/workflows/docs.yml`  
Runs on push to `main` and `workflow_dispatch`.  
Build env:

```
PUBLIC_SITE_URL=https://goshikavs.github.io
PUBLIC_BASE_PATH=/goshikq-agent-framework/
```

Artifact: `apps/website/dist`  
Expected URL: https://goshikavs.github.io/goshikq-agent-framework/

## Owner steps (not executed in engineering)

1. Repo Settings → Pages → Source: **GitHub Actions**.
2. Protect the `github-pages` environment if reviewers should approve deploys.
3. Merge `release/v1.0-hardening` to `main` **only after an explicit merge approval**.
4. Confirm the `Docs` workflow deploys and the URL returns 200.
5. Set the GitHub repository Website field to that URL.

Do not deploy from this branch automatically except via the existing workflow after merge.

VitePress under `docs/site` remains a local/CI documentation build. It is **not** the Pages artifact after this change.
