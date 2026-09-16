function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `/api${p}`;
}

export async function recordVisit(ref) {
  const res = await fetch(apiUrl("/public/xfashion/visit"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ref }),
  });
  if (!res.ok) return { recorded: false };
  return res.json();
}

export async function submitLead(body) {
  const res = await fetch(apiUrl("/public/xfashion/lead"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg =
      typeof d === "string"
        ? d
        : Array.isArray(d)
          ? d.map((x) => x.msg || x).join("; ")
          : data.message || "Не удалось отправить заявку";
    throw new Error(msg);
  }
  return data;
}
