const TOKEN_KEY = "antrasha_gift_token";
const ROLE_KEY = "antrasha_gift_role";
const PERMS_KEY = "antrasha_gift_permissions";
const NAME_KEY = "antrasha_gift_name";

const BACKEND_ORIGIN = (import.meta.env.VITE_BACKEND_ORIGIN || "").replace(/\/$/, "");

export function apiUrl(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (BACKEND_ORIGIN) return `${BACKEND_ORIGIN}${normalized}`;
  return `/api${normalized}`;
}

function detail(data, fallback) {
  const value = data?.detail;
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((item) => item.msg || JSON.stringify(item)).join("\n");
  return fallback;
}

async function parseResponseJson(res) {
  if (res.status === 401 && getToken()) {
    clearSession();
    if (!window.location.pathname.startsWith("/certificates/")) {
      window.location.replace("/login");
    }
    throw new Error("Сессия истекла");
  }
  const text = await res.text();
  if (res.status === 204 || !text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Ответ не JSON (HTTP ${res.status})`);
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function isAccessTokenExpired(token) {
  try {
    const part = token.split(".")[1];
    if (!part) return true;
    const payload = JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
    if (!payload.exp) return false;
    return payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function hasValidSession() {
  const token = getToken();
  if (!token) return false;
  if (isAccessTokenExpired(token)) {
    clearSession();
    return false;
  }
  return true;
}

export function setSession(token, role, permissions = [], displayName = "") {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role || "");
  localStorage.setItem(PERMS_KEY, JSON.stringify(permissions || []));
  if (displayName) localStorage.setItem(NAME_KEY, displayName);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(PERMS_KEY);
  localStorage.removeItem(NAME_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function getDisplayName() {
  return localStorage.getItem(NAME_KEY) || "";
}

export function getPermissions() {
  if (getRole() === "superuser") return ["giftcards"];
  try {
    const parsed = JSON.parse(localStorage.getItem(PERMS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

export function hasGiftAccess() {
  if (getRole() === "superuser") return true;
  return getPermissions().includes("giftcards");
}

function authHeaders(json = false) {
  const headers = {};
  if (json) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function loginWorker(phone, pin) {
  const res = await fetch(apiUrl("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, pin }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (data.role !== "worker" && data.role !== "superuser") {
    throw new Error("Нет доступа: только сотрудники.");
  }
  const perms = Array.isArray(data.permissions) ? data.permissions.map(String) : [];
  if (data.role === "worker" && !perms.includes("giftcards")) {
    throw new Error("Нет доступа: включите право «Сертификаты» в админке.");
  }
  return data;
}

export async function fetchAdminMe() {
  const res = await fetch(apiUrl("/admin/me"), { headers: authHeaders() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

async function request(path, { method = "GET", body, query } = {}) {
  const params = query
    ? `?${new URLSearchParams(
        Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== ""),
      )}`
    : "";
  const res = await fetch(`${apiUrl(path)}${params}`, {
    method,
    headers: authHeaders(body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export function listCertificates() {
  return request("/gift-certificates/");
}

export function createCertificate(body) {
  return request("/gift-certificates/", { method: "POST", body });
}

export function sendConfirmCode(id, chargeSum) {
  return request(`/gift-certificates/send-confirm-code/${id}`, {
    method: "POST",
    query: { charge_sum: chargeSum },
  });
}

export function chargeCertificate(id, confirmCode) {
  return request(`/gift-certificates/charge/${id}`, {
    method: "POST",
    query: { confirm_code: confirmCode },
  });
}

export function sendTelegram(id, chatId) {
  return request(`/gift-certificates/send-telegram/${id}`, {
    method: "POST",
    body: { chat_id: Number(chatId) },
  });
}

export async function fetchPublicCertificate(id) {
  const res = await fetch(apiUrl(`/gift-certificates/${id}`));
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, "Сертификат не найден"));
  return data;
}
