import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const dist = resolve("dist/index.html");
if (!existsSync(dist)) {
  console.error("missing dist/index.html");
  process.exit(1);
}
const html = readFileSync(dist, "utf8");
const required = ["/goshikq-agent-framework/", "goshikavs.github.io/goshikq-agent-framework"];
for (const token of required) {
  if (!html.includes(token)) {
    console.error(`GitHub Pages HTML missing ${token}`);
    process.exit(1);
  }
}
if (/<meta[^>]+name=["']robots["'][^>]+noindex/i.test(html)) {
  console.error("index.html contains noindex");
  process.exit(1);
}
if (!html.includes("goshikavs.github.io/goshikq-agent-framework/")) {
  console.error("canonical host+base missing from index.html");
  process.exit(1);
}
console.log("GitHub Pages base-path HTML looks correct");
