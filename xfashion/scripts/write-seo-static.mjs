#!/usr/bin/env node
/** Пишет robots.txt и sitemap.xml с актуальным origin (сборка / prebuild). */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const publicDir = path.join(root, "public");
const articlesPath = path.join(root, "src/content/articles.js");

const origin = (process.env.VITE_SITE_ORIGIN || "https://xfashion.pro").replace(/\/$/, "");

const raw = fs.readFileSync(articlesPath, "utf8");
const slugs = [...raw.matchAll(/slug:\s*"([^"]+)"/g)].map((m) => m[1]);

const urls = [
  { loc: `${origin}/`, priority: "1.0", changefreq: "weekly" },
  { loc: `${origin}/blog`, priority: "0.8", changefreq: "weekly" },
  ...slugs.map((slug) => ({
    loc: `${origin}/blog/${slug}`,
    priority: "0.7",
    changefreq: "monthly",
  })),
];

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) => `  <url>
    <loc>${u.loc}</loc>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`,
  )
  .join("\n")}
</urlset>
`;

const robots = `User-agent: *
Allow: /

Sitemap: ${origin}/sitemap.xml
`;

fs.writeFileSync(path.join(publicDir, "sitemap.xml"), sitemap);
fs.writeFileSync(path.join(publicDir, "robots.txt"), robots);
console.log(`[seo-static] origin=${origin}, urls=${urls.length}`);
