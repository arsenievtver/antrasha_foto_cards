import { useEffect } from "react";
import { siteUrl } from "../config/siteOrigin.js";

export default function PageMeta({ title, description, canonicalPath = "/" }) {
  useEffect(() => {
    if (title) document.title = title;
    if (description) {
      let el = document.querySelector('meta[name="description"]');
      if (el) el.setAttribute("content", description);
    }
    const href = siteUrl(canonicalPath);
    let link = document.querySelector('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "canonical";
      document.head.appendChild(link);
    }
    link.href = href;
    for (const sel of ['meta[property="og:url"]', 'meta[property="og:image"]']) {
      const meta = document.querySelector(sel);
      if (!meta) continue;
      const prop = meta.getAttribute("property");
      if (prop === "og:url") meta.setAttribute("content", href);
      if (prop === "og:image") meta.setAttribute("content", siteUrl("/how/model.jpg"));
    }
  }, [title, description, canonicalPath]);

  return null;
}
