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

## Current status (2026-11-20)

PR #27 merged to `main`. `docs.yml` deploys Astro. The repository Website field is `https://goshikavs.github.io/goshikq-agent-framework/`.

Further deploys happen on push to `main` (or `workflow_dispatch`) through the existing workflow. Do not purchase a domain or change DNS.

VitePress under `docs/site` remains a local/CI documentation build. It is **not** the Pages artifact.
