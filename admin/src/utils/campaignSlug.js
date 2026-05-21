/** Превью slug на клиенте (та же логика, что normalize_campaign_slug на бэкенде). */
export function previewSlugFromText(raw) {
  if (!raw?.trim()) return "";
  let s = raw.trim().toLowerCase().replace(/\s+/g, "_");
  s = s.replace(/[^a-z0-9_-]+/g, "");
  s = s.replace(/_+/g, "_").replace(/^_|_$/g, "");
  return s;
}

export function isValidSlug(s) {
  return /^[a-z0-9][a-z0-9_-]{0,62}$/.test(s);
}
