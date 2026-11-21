# Website deployment

Do not purchase a domain, change DNS, or connect production hosting until the owner approves.

## Intended host: Cloudflare Pages (free tier)

1. Cloudflare Dashboard → Workers & Pages → Create → Pages.
2. Connect GitHub repository `goshikavs/goshikq-agent-framework`.
3. Project name: `goshikq` (this becomes `goshikq.pages.dev` if available).
4. Build settings:

| Setting | Value |
| --- | --- |
| Root directory | `apps/website` |
| Build command | `bun install && bun run build` |
| Build output | `dist` |
| Node / Bun | Enable Bun, or use the Cloudflare Bun build image |
| Environment | `PUBLIC_SITE_URL=https://<project>.pages.dev` (later the custom domain) |

5. Preview deployments: enable for pull requests if the Cloudflare GitHub app is connected.
6. Custom domain (later): add `www` or apex in Cloudflare DNS as CNAME/ALIAS to the pages.dev target. HTTPS is automatic.

Rollback: Cloudflare Pages → Deployments → previous successful deploy → Retry / Rollback.

## GitHub Pages (current public host)

`.github/workflows/docs.yml` builds `apps/website` and deploys `apps/website/dist` from `main`.

Public URL: https://goshikavs.github.io/goshikq-agent-framework/

VitePress under `docs/site` is a local/CI documentation build. It is not the Pages artifact. Do not run a second VitePress Pages job on the same hostname.

## Local production build

```bash
cd apps/website
PUBLIC_SITE_URL=http://127.0.0.1:4321 bun run build
bun run preview
```
