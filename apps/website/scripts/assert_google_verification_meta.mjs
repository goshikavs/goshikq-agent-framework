import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const expected = String(process.env.PUBLIC_GOOGLE_SITE_VERIFICATION || "").trim();
if (!expected) {
  console.error("assert_google_verification_meta: PUBLIC_GOOGLE_SITE_VERIFICATION must be set");
  process.exit(1);
}
if (/^PASTE_TOKEN_HERE$/i.test(expected) || /invent/i.test(expected)) {
  console.error("assert_google_verification_meta: refusing a placeholder token");
  process.exit(1);
}

const dist = resolve("dist/index.html");
if (!existsSync(dist)) {
  console.error("missing dist/index.html");
  process.exit(1);
}
const html = readFileSync(dist, "utf8");
if (!/<head[\s>]/i.test(html)) {
  console.error("index.html has no <head>");
  process.exit(1);
}
const tag =
  /<meta\s+name=["']google-site-verification["']\s+content=["']([^"']+)["']\s*\/?>/i.exec(html) ||
  /<meta\s+content=["']([^"']+)["']\s+name=["']google-site-verification["']\s*\/?>/i.exec(html);
if (!tag) {
  console.error("index.html is missing google-site-verification meta in the generated homepage");
  process.exit(1);
}
if (tag[1] !== expected) {
  console.error(`verification content mismatch: got ${JSON.stringify(tag[1])}, expected ${JSON.stringify(expected)}`);
  process.exit(1);
}
if (/<meta[^>]+name=["']robots["'][^>]+noindex/i.test(html)) {
  console.error("index.html contains noindex");
  process.exit(1);
}
if (!/rel=["']canonical["']/i.test(html)) {
  console.error("index.html lost rel=canonical");
  process.exit(1);
}
console.log("google-site-verification meta is present on the generated homepage");
