export function digitsOnly(s) {
  return String(s || "").replace(/\D/g, "");
}

export function formatPhoneMask(raw) {
  const rawDigits = digitsOnly(raw);
  if (!rawDigits) return "";
  let d = rawDigits;
  if (d.startsWith("8")) d = "7" + d.slice(1);
  if (d.startsWith("9") && d.length <= 10) d = "7" + d;
  if (!d.startsWith("7")) d = "7" + d.replace(/^7+/, "");
  d = d.slice(0, 11);
  const rest = d.slice(1);
  let out = "+7";
  if (rest.length === 0) return out;
  out += " (" + rest.slice(0, 3);
  if (rest.length <= 3) return out;
  out += ") " + rest.slice(3, 6);
  if (rest.length <= 6) return out;
  out += "-" + rest.slice(6, 8);
  if (rest.length <= 8) return out;
  out += "-" + rest.slice(8, 10);
  return out;
}

export function normalizePhoneRu(masked) {
  let d = digitsOnly(masked);
  if (d.startsWith("8")) d = "7" + d.slice(1);
  if (d.startsWith("9") && d.length === 10) d = "7" + d;
  if (d.length === 11 && d.startsWith("7")) return "+" + d;
  return null;
}
