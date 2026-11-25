export const SITE = {
  name: "Goshikq",
  legalName: "Goshikq",
  tagline: "Build Agents. Verify Outcomes.",
  headline: "Build AI Agents. Verify Real Outcomes.",
  description:
    "Open-source AI agent framework with a Rust runtime for durable execution, multi-agent orchestration, and evidence-backed business outcome verification. Python and TypeScript SDKs. Apache 2.0.",
  version: "1.0.0-rc.2",
  milestone: "v1.0.0-rc.2",
  statusLabel: "Release candidate",
  github: "https://github.com/goshikavs/goshikq-agent-framework",
  githubGit: "https://github.com/goshikavs/goshikq-agent-framework.git",
  githubPrerelease: "https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0-rc.2",
  githubPrereleaseAssets: "https://github.com/goshikavs/goshikq-agent-framework/releases/download/v1.0.0-rc.2",
  zipMain: "https://github.com/goshikavs/goshikq-agent-framework/archive/refs/heads/main.zip",
  licenseUrl: "https://github.com/goshikavs/goshikq-agent-framework/blob/main/LICENSE",
  securityUrl: "https://github.com/goshikavs/goshikq-agent-framework/blob/main/SECURITY.md",
  contributingUrl: "https://github.com/goshikavs/goshikq-agent-framework/blob/main/CONTRIBUTING.md",
  ciUrl: "https://github.com/goshikavs/goshikq-agent-framework/actions/workflows/ci.yml",
  ciBadge: "https://github.com/goshikavs/goshikq-agent-framework/actions/workflows/ci.yml/badge.svg",
  pagesDocs: "https://goshikavs.github.io/goshikq-agent-framework/",
  maintainer: "https://github.com/goshikavs",
  pythonPackage: "goshikq-ai",
  pythonVersion: "1.0.0",
  tsPackage: "@goshikq/sdk",
  tsVersion: "1.0.0",
  runtime: "goshikq-server",
  studioPort: "http://127.0.0.1:3000",
  runtimePort: "http://127.0.0.1:7400",
} as const;

export const NAV = [
  { href: "/features/", label: "Product" },
  { href: "/docs/", label: "Documentation" },
  { href: "/quickstart/", label: "Quickstart" },
  { href: "/download/", label: "Install" },
  { href: "/examples/", label: "Examples" },
  { href: "/architecture/", label: "Architecture" },
  { href: "/studio/", label: "Studio" },
  { href: "/community/", label: "Community" },
] as const;

/** Prefix an in-site path with Astro `base` (GitHub Pages `/goshikq-agent-framework/`). */
export function withBase(path: string): string {
  if (/^(https?:|mailto:|#)/i.test(path)) {
    return path;
  }
  const base = import.meta.env.BASE_URL || "/";
  if (path === "/" || path === "") {
    return base;
  }
  return `${base}${path.replace(/^\//, "")}`;
}

export function canonicalUrl(path: string, site: string): string {
  return new URL(withBase(path), site.endsWith("/") ? site : `${site}/`).href;
}
