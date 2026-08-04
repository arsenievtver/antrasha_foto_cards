const TOKEN_KEY = "antrasha_work_token";
const ROLE_KEY = "antrasha_work_role";
const PERMS_KEY = "antrasha_work_permissions";

const BACKEND_ORIGIN = (import.meta.env.VITE_BACKEND_ORIGIN || "").replace(/\/$/, "");

export function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (BACKEND_ORIGIN) return `${BACKEND_ORIGIN}${p}`;
  return `/api${p}`;
}

async function parseResponseJson(res) {
  if (res.status === 401 && getToken()) {
    redirectToLogin();
    throw new Error("Сессия истекла");
  }
  const text = await res.text();
  if (res.status === 204 || !text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    const snippet = text.slice(0, 200).replace(/\s+/g, " ").trim();
    throw new Error(
      `Ответ не JSON (HTTP ${res.status}).` + (snippet ? ` ${snippet}` : ""),
    );
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
  const t = getToken();
  if (!t) return false;
  if (isAccessTokenExpired(t)) {
    clearSession();
    return false;
  }
  return true;
}

function redirectToLogin() {
  clearSession();
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  if (path !== "/login") {
    window.location.replace("/login");
  }
}

export function setSession(token, role, permissions = []) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
  if (role) localStorage.setItem(ROLE_KEY, role);
  else localStorage.removeItem(ROLE_KEY);
  if (permissions?.length) {
    localStorage.setItem(PERMS_KEY, JSON.stringify(permissions));
  } else {
    localStorage.removeItem(PERMS_KEY);
  }
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(PERMS_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function getPermissions() {
  if (getRole() === "superuser") {
    return ["product", "outlet", "outlet_transfer", "ai_assistant"];
  }
  try {
    const raw = localStorage.getItem(PERMS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

export function hasPermission(key) {
  if (getRole() === "superuser") return true;
  return getPermissions().includes(key);
}

export function hasProductAccess() {
  return hasPermission("product");
}

export function hasOutletAccess() {
  return hasPermission("outlet");
}

export function hasOutletTransferAccess() {
  return hasPermission("outlet_transfer");
}

export function hasAiAssistantAccess() {
  return hasPermission("ai_assistant");
}

/** Вход в work PWA: закупки, аутлет, перенос и/или AI. */
export function hasWorkAccess() {
  return (
    hasProductAccess() ||
    hasOutletAccess() ||
    hasOutletTransferAccess() ||
    hasAiAssistantAccess()
  );
}

export function workHomePath() {
  if (hasProductAccess()) return "/dashboard";
  if (hasOutletAccess() || hasOutletTransferAccess() || hasAiAssistantAccess()) {
    return "/menu";
  }
  return "/login";
}

/** Актуальные роль/права (как в админке) — без повторного логина. */
export async function fetchAdminMe() {
  const res = await fetch(apiUrl("/admin/me"), { headers: headersAuthOnly() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

function detail(data, fallback) {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("\n");
  return fallback;
}

function headersJson() {
  const h = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
}

function headersAuthOnly() {
  const h = {};
  const t = getToken();
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
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
  if (
    data.role === "worker" &&
    !perms.includes("product") &&
    !perms.includes("outlet") &&
    !perms.includes("outlet_transfer") &&
    !perms.includes("ai_assistant")
  ) {
    throw new Error(
      "Нет доступа: включите нужное право сотрудника в админке (Товар / Аутлет / AI помощник).",
    );
  }
  return data;
}

async function request(path, { method = "GET", body, query } = {}) {
  const qs = query
    ? `?${new URLSearchParams(
        Object.entries(query).filter(
          ([, v]) => v !== undefined && v !== null && v !== "",
        ),
      )}`
    : "";
  const res = await fetch(`${apiUrl(path)}${qs}`, {
    method,
    headers: headersJson(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) {
    if (!res.ok) throw new Error(res.statusText);
    return null;
  }
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export function fetchProcurementRefs() {
  return request("/admin/procurement/refs");
}

export function fetchOrderGuidance() {
  return request("/admin/procurement/order-guidance");
}

export function fetchSeasonDashboard(seasonId) {
  return request("/admin/procurement/season-dashboard", {
    query: seasonId ? { season_id: seasonId } : undefined,
  });
}

export function createBrand(name) {
  return request("/admin/brands", { method: "POST", body: { name } });
}

export function fetchBrandOrders(query) {
  return request("/admin/brand-orders", { query });
}

export function fetchBrandOrder(orderId) {
  return request(`/admin/brand-orders/${orderId}`);
}

export function createBrandOrder(body) {
  return request("/admin/brand-orders", { method: "POST", body });
}

export function updateBrandOrder(orderId, body) {
  return request(`/admin/brand-orders/${orderId}`, { method: "PATCH", body });
}

export function fetchPayments(query) {
  return request("/admin/payments", { query });
}

export function fetchPayment(paymentId) {
  return request(`/admin/payments/${paymentId}`);
}

export function createPayment(body) {
  return request("/admin/payments", { method: "POST", body });
}

export function updatePayment(paymentId, body) {
  return request(`/admin/payments/${paymentId}`, { method: "PATCH", body });
}

export function fetchShipments(query) {
  return request("/admin/shipments", { query });
}

export function fetchShipment(shipmentId) {
  return request(`/admin/shipments/${shipmentId}`);
}

export function createShipment(body) {
  return request("/admin/shipments", { method: "POST", body });
}

export function updateShipment(shipmentId, body) {
  return request(`/admin/shipments/${shipmentId}`, { method: "PATCH", body });
}

export async function fetchOutletPhotoStatus() {
  const res = await fetch(apiUrl("/admin/outlet-photo/status"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function lookupOutletPhotoBarcode(barcode) {
  const res = await fetch(apiUrl("/admin/outlet-photo/lookup"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ barcode }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function generateOutletPhoto(gender, file) {
  const fd = new FormData();
  fd.append("gender", gender);
  fd.append("image", file);
  const res = await fetch(apiUrl("/admin/outlet-photo/generate"), {
    method: "POST",
    headers: headersAuthOnly(),
    body: fd,
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function uploadOutletPhotoToMoySklad({
  productId,
  filename,
  content,
  name,
  article,
  code,
  barcode,
  pathName,
  gender,
}) {
  const res = await fetch(apiUrl("/admin/outlet-photo/upload"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({
      product_id: productId,
      filename,
      content,
      name: name || null,
      article: article || null,
      code: code || null,
      barcode: barcode || null,
      path_name: pathName || null,
      gender: gender || null,
    }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

/** @param {"pending"|"transferred"|"all"} [filter] */
export async function fetchOutletPhotoUploads({ filter = "pending", skip = 0, limit = 50 } = {}) {
  const q = new URLSearchParams({
    filter,
    skip: String(skip),
    limit: String(limit),
  });
  const res = await fetch(apiUrl(`/admin/outlet-photo/uploads?${q}`), {
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function setOutletPhotoUploadTransferred(uploadId, transferred) {
  const res = await fetch(apiUrl(`/admin/outlet-photo/uploads/${uploadId}`), {
    method: "PATCH",
    headers: headersJson(),
    body: JSON.stringify({ transferred: Boolean(transferred) }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchWarehouseAiStatus() {
  const res = await fetch(apiUrl("/admin/warehouse-ai/status"), {
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchWarehouseAiPresets() {
  const res = await fetch(apiUrl("/admin/warehouse-ai/presets"), {
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function postWarehouseAiChat({ messages, preset_id } = {}) {
  const res = await fetch(apiUrl("/admin/warehouse-ai/chat"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({
      messages,
      preset_id: preset_id || null,
    }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}
