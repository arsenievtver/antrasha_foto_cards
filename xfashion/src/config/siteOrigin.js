/** Публичный origin лендинга (canonical, JSON-LD). В браузере — текущий origin. */
export function getSiteOrigin() {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  const fromEnv = (import.meta.env.VITE_SITE_ORIGIN || "").trim();
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  return "https://xfashion.pro";
}

export function siteUrl(path = "/") {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${getSiteOrigin()}${p}`;
}
