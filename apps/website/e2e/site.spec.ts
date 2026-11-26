import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const RELEASE = "https://github.com/goshikavs/goshikq-agent-framework/releases/tag/v1.0.0";
const ASSETS = "https://github.com/goshikavs/goshikq-agent-framework/releases/download/v1.0.0";

test.describe("Goshikq website", () => {
  test("homepage has Goshikq branding and no Axiom chrome", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Build AI Agents/i })).toBeVisible();
    await expect(page.getByRole("link", { name: "Get started" }).first()).toBeVisible();
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/Axiom Studio/i);
    expect(body).toMatch(/Goshikq/);
    expect(body).toMatch(/Stable/);
  });

  test("homepage HTML is meaningful without waiting on demo JS", async ({ page }) => {
    const res = await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    const html = await page.content();
    expect(html).toMatch(/<h1>/i);
    expect(html).toMatch(/Verify Real Outcomes/i);
    expect(html).not.toMatch(/noindex/i);
    expect(html).toMatch(/rel="canonical"/i);
    expect(html).not.toMatch(/google-site-verification/i);
  });

  test("download identifies the stable GitHub release and unpublished registries", async ({ page }) => {
    await page.goto("/download/");
    await expect(page.getByText(/stable GitHub Release/i).first()).toBeVisible();
    await expect(page.getByText(/Windows ARM64 is experimental/i).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Open the GitHub release/i })).toHaveAttribute(
      "href",
      RELEASE,
    );
    await expect(page.getByRole("link", { name: /main\.zip/i })).toHaveAttribute(
      "href",
      "https://github.com/goshikavs/goshikq-agent-framework/archive/refs/heads/main.zip",
    );
    await expect(page.locator('a[href*="/releases/download/v1.0.0/"]')).not.toHaveCount(0);
    await expect(page.locator('a[href*="/releases/download/v1.0.0-rc.2/"]')).toHaveCount(0);
    await expect(page.locator('a[href*="/releases/download/v1.0.0-rc.1/"]')).toHaveCount(0);
    await expect(page.locator('a[href*="pypi.org/project"]')).toHaveCount(0);
    await expect(page.locator('a[href*="crates.io"]')).toHaveCount(0);
  });

  test("published stable download links resolve", async ({ request, page }) => {
    test.setTimeout(90_000);
    await page.goto("/download/");
    const hrefs = await page.locator('a[href*="/releases/download/v1.0.0/"]').evaluateAll((els) =>
      els.map((el) => (el as HTMLAnchorElement).href),
    );
    expect(hrefs.length).toBeGreaterThan(5);
    expect(hrefs.every((h) => h.includes("/releases/download/v1.0.0/"))).toBeTruthy();
    let body = "";
    let last = "no response";
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const sums = await request.get(`${ASSETS}/SHA256SUMS`, { timeout: 20_000 });
        if (sums.ok()) {
          body = await sums.text();
          break;
        }
        last = `HTTP ${sums.status()}`;
      } catch (err) {
        last = String(err);
      }
    }
    expect(body, `published SHA256SUMS was not readable: ${last}`).toMatch(
      /goshikq-1\.0\.0-linux-amd64\.tar\.gz/,
    );
    expect(body).toMatch(/goshikq-1\.0\.0-windows-arm64\.zip/);
    expect(body).toMatch(/40ecd97e8bb1cab931b718b78be5bdc6cd26e6021a5ef1a1d275f4ca98cf1da9/);
  });

  test("docs landing and search UI exist", async ({ page }) => {
    await page.goto("/docs/");
    await expect(page.getByRole("heading", { name: /Goshikq documentation/i })).toBeVisible();
    await expect(page.locator("body")).toContainText("Getting started");
    await expect(page.getByRole("button", { name: /Search/i }).first()).toBeVisible();
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/Astro \+ Starlight/);
    expect(body).not.toMatch(/currently deployed documentation host/i);
    expect(body).not.toMatch(/until the public website cutover/i);
    expect(body).not.toMatch(/Alpha software/i);
  });

  test("homepage SEO title, description, and stable release copy", async ({ page }) => {
    const res = await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(res?.ok()).toBeTruthy();
    await expect(page).toHaveTitle(/Goshikq/);
    const description = await page.locator('meta[name="description"]').getAttribute("content");
    expect(description).toMatch(/Rust runtime/i);
    const html = await page.content();
    expect(html).toMatch(/rel="canonical"/i);
    expect(html).not.toMatch(/noindex/i);
    expect(html).not.toMatch(/Alpha software/i);
    expect(html).not.toMatch(/google-site-verification/i);
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/Stable 1\.0\.0/);
    expect(body).toMatch(/Stable v1\.0\.0 is the GitHub Release/);
    expect(body).not.toMatch(/v1\.0 is not ready/);
  });

  test("documentation search dialog accepts a query", async ({ page }) => {
    await page.goto("/docs/");
    await page.getByRole("button", { name: /Search/i }).first().click();
    const input = page.locator("input[type='search'], input[type='text'][placeholder*='Search' i], .pagefind-ui__search-input").first();
    await expect(input).toBeVisible();
    await input.fill("verification");
    await expect(page.locator("body")).toContainText(/verification/i);
  });

  test("marketing pages render titles, canonicals, and no noindex", async ({ page }) => {
    const paths = [
      "/features/",
      "/architecture/",
      "/quickstart/",
      "/community/",
      "/examples/",
      "/examples/refund-verification/",
      "/examples/insurance-claims/",
      "/studio/",
      "/download/",
    ];
    for (const path of paths) {
      const res = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(res?.ok(), path).toBeTruthy();
      await expect(page.locator("h1"), path).toHaveCount(1);
      const html = await page.content();
      expect(html, path).toMatch(/rel="canonical"/i);
      expect(html, path).not.toMatch(/noindex/i);
    }
  });

  test("layout does not overflow the viewport", async ({ page }) => {
    for (const path of ["/", "/download/", "/studio/", "/docs/"]) {
      await page.goto(path);
      const box = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
      }));
      expect(box.scroll, `${path} ${JSON.stringify(box)}`).toBeLessThanOrEqual(box.client + 2);
    }
  });

  test("studio gallery screenshots load", async ({ page }) => {
    await page.goto("/studio/");
    const img = page.locator("img[src*='goshikq-studio-dashboard']").first();
    await expect(img).toBeVisible();
    const res = await page.request.get("/media/studio/goshikq-studio-dashboard.webp");
    expect(res.ok()).toBeTruthy();
    await img.click();
    await expect(page.getByRole("dialog", { name: "Screenshot" })).toBeVisible();
  });

  test("keyboard can reach skip link and primary nav", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  });

  test("primary navigation matches the viewport", async ({ page }, testInfo) => {
    await page.goto("/");
    const menu = page.getByRole("button", { name: "Menu" });
    const docs = page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Documentation" });
    if (testInfo.project.name === "mobile") {
      await expect(menu).toBeVisible();
      await expect(menu).toHaveAttribute("aria-expanded", "false");
      await menu.click();
      await expect(menu).toHaveAttribute("aria-expanded", "true");
      await expect(docs).toBeVisible();
      await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Install" }).click();
      await expect(page).toHaveURL(/\/download\/$/);
    } else {
      await expect(menu).toBeHidden();
      await expect(docs).toBeVisible();
      await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Install" }).click();
      await expect(page).toHaveURL(/\/download\/$/);
    }
  });

  test("internal marketing links return 200", async ({ page, request }) => {
    await page.goto("/");
    const hrefs = await page.locator("a[href]").evaluateAll((els) =>
      [...new Set(els.map((el) => (el as HTMLAnchorElement).getAttribute("href") || ""))]
        .filter((h) => h.startsWith("/") && !h.startsWith("//")),
    );
    expect(hrefs.length).toBeGreaterThan(5);
    for (const href of hrefs.slice(0, 20)) {
      const res = await request.get(href);
      expect(res.status(), href).toBeLessThan(400);
    }
  });

  test("accessibility landmarks and image alternatives", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveCount(1);
    const missingAlt = await page.locator("img:not([alt])").count();
    expect(missingAlt).toBe(0);
    const metrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      return {
        dcl: nav ? Math.round(nav.domContentLoadedEventEnd) : -1,
        load: nav ? Math.round(nav.loadEventEnd) : -1,
      };
    });
    expect(metrics.dcl, JSON.stringify(metrics)).toBeGreaterThan(0);
    expect(metrics.dcl).toBeLessThan(20_000);
  });
});

test.describe("build artifacts", () => {
  test("robots.txt allows indexing", async ({ request }) => {
    const res = await request.get("/robots.txt");
    expect(res.ok()).toBeTruthy();
    const text = await res.text();
    expect(text).toMatch(/Allow:\s*\//);
    expect(text).not.toMatch(/Disallow:\s*\//);
    expect(text).not.toMatch(/noindex/i);
    expect(text).toMatch(/Sitemap:/);
  });

  test("sitemap exists", async ({ request }) => {
    const res = await request.get("/sitemap-index.xml");
    expect(res.ok()).toBeTruthy();
    const xml = await res.text();
    expect(xml).toMatch(/sitemap/i);
    const child = xml.match(/https?:\/\/[^<]+sitemap[^<]*\.xml/)?.[0];
    expect(child).toBeTruthy();
    const pages = await request.get(new URL(child!, "http://127.0.0.1:4321").pathname);
    expect(pages.ok()).toBeTruthy();
    const body = await pages.text();
    expect(body).toMatch(/download/);
    expect(body).toMatch(/docs/);
  });
});

test("download clone command matches the public repo", async () => {
  const site = readFileSync(resolve("src/lib/site.ts"), "utf8");
  expect(site).toContain("https://github.com/goshikavs/goshikq-agent-framework.git");
  expect(site).toContain(RELEASE);
  expect(site).not.toContain("pypi.org/project");
});
