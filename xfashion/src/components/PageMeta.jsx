import { useEffect } from "react";

export default function PageMeta({ title, description, canonicalPath = "/" }) {
  useEffect(() => {
    if (title) document.title = title;
    if (description) {
      let el = document.querySelector('meta[name="description"]');
      if (el) el.setAttribute("content", description);
    }
    const href = `https://xfashion.pro${canonicalPath.startsWith("/") ? canonicalPath : `/${canonicalPath}`}`;
    let link = document.querySelector('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "canonical";
      document.head.appendChild(link);
    }
    link.href = href;
  }, [title, description, canonicalPath]);

  return null;
}
