import type { APIRoute } from "astro";
import { canonicalUrl } from "../lib/site";

export const GET: APIRoute = ({ site }) => {
  const origin = site?.href ?? "https://goshikavs.github.io";
  const sitemap = canonicalUrl("/sitemap-index.xml", origin);
  const body = `User-agent: *\nAllow: /\n\nSitemap: ${sitemap}\n`;
  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
};
