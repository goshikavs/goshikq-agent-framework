#!/usr/bin/env python3
"""Fail CI if *current* public docs still describe a pre-cutover website.

Historical milestone reports, dated audits, and the local VitePress tree are
not scanned. Only files that describe today's public status are checked.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files that describe the live product, website, or current prerelease.
ACTIVE = [
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "apps" / "website" / "src" / "content" / "docs" / "docs" / "index.mdx",
    ROOT / "apps" / "website" / "src" / "content" / "docs" / "docs" / "getting-started.mdx",
    ROOT / "apps" / "website" / "src" / "content" / "docs" / "docs" / "python-sdk.mdx",
    ROOT / "apps" / "website" / "src" / "lib" / "site.ts",
    ROOT / "apps" / "website" / "src" / "pages" / "index.astro",
    ROOT / "apps" / "website" / "src" / "pages" / "download.astro",
    ROOT / "docs" / "IMPLEMENTATION_STATUS.md",
    ROOT / "docs" / "FEATURE_MATRIX.md",
    ROOT / "docs" / "guides" / "search-console.md",
    ROOT / "docs" / "release" / "v1.0.0-rc.2-notes.md",
    ROOT / "docs" / "website" / "architecture.md",
    ROOT / "docs" / "website" / "deployment.md",
    ROOT / "docs" / "website" / "github-pages.md",
    ROOT / "docs" / "website" / "quality-report.md",
    ROOT / "docs" / "website" / "search-console-setup.md",
    ROOT / "docs" / "website" / "search-engine-setup.md",
]

# Phrases that mean the Astro site is not yet public. Allowed in
# docs/milestones/, docs/audits/, docs/site/, and dated readiness audits.
STALE_DEPLOYMENT = [
    "not deployed until owner approval",
    "until the public website cutover",
    "remains the currently deployed",
    "still publishes **VitePress**",
    "still publishes VitePress",
    "still serves the previous VitePress",
    "VitePress GitHub Pages still the live",
    "docs.yml` workflow still publishes",
    "**NOT_RUN** until owner merges",
    "Alpha software",
]

errors: list[str] = []


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fail(msg: str) -> None:
    errors.append(msg)


def main() -> int:
    for path in ACTIVE:
        if not path.is_file():
            fail(f"missing active docs file: {rel(path)}")
            continue
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for phrase in STALE_DEPLOYMENT:
            if phrase.lower() in lower:
                fail(f"{rel(path)} still contains stale deployment copy: {phrase!r}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "goshikavs.github.io/goshikq-agent-framework" not in readme:
        fail("README.md must link the live GitHub Pages URL")
    if "not deployed until" in readme.lower():
        fail("README.md must not say the website is undeployed")

    index = (ROOT / "apps" / "website" / "src" / "content" / "docs" / "docs" / "index.mdx").read_text(
        encoding="utf-8"
    )
    if "Astro" not in index:
        fail("docs index.mdx must identify Astro as the live docs host")
    if "currently deployed documentation host" in index:
        fail("docs index.mdx must not claim VitePress is still the live host")

    home = (ROOT / "apps" / "website" / "src" / "pages" / "index.astro").read_text(encoding="utf-8")
    if "v1.0 is not ready" in home:
        fail("homepage must not use 'v1.0 is not ready'; say stable v1.0.0 is unpublished")
    if "Stable v1.0.0 is not published" not in home:
        fail("homepage limitations must say stable v1.0.0 is not published")

    deploy = (ROOT / "docs" / "website" / "deployment.md").read_text(encoding="utf-8")
    if "apps/website" not in deploy or "docs.yml" not in deploy:
        fail("docs/website/deployment.md must describe docs.yml deploying apps/website")

    search = (ROOT / "docs" / "guides" / "search-console.md").read_text(encoding="utf-8")
    if "docs/site/.vitepress" in search:
        fail("docs/guides/search-console.md must not send verification tokens to VitePress")
    if "sitemap-index.xml" not in search:
        fail("docs/guides/search-console.md must submit sitemap-index.xml")

    status = (ROOT / "docs" / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    if "Astro + Starlight" not in status:
        fail("IMPLEMENTATION_STATUS.md available inventory must name Astro + Starlight")

    if errors:
        print("assert_public_docs failed:", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(f"public docs ok: {len(ACTIVE)} active files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
