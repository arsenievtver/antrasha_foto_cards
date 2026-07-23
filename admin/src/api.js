const TOKEN_KEY = "antrasha_admin_token";
const ROLE_KEY = "antrasha_admin_role";

/** Пусто = dev через Vite proxy `/api` → бэкенд. Иначе прямой URL API, например http://127.0.0.1:8000 */
const BACKEND_ORIGIN = (import.meta.env.VITE_BACKEND_ORIGIN || "").replace(/\/$/, "");

/**
 * Путь к эндпоинту бэкенда без префикса /api: `/admin/stats`, `/auth/login`.
 * В dev: `/api` + путь; с VITE_BACKEND_ORIGIN: origin + путь.
 */
export function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (BACKEND_ORIGIN) return `${BACKEND_ORIGIN}${p}`;
  return `/api${p}`;
}

/** Не глотать HTML/текст от nginx как пустой JSON — иначе очереди и списки «пустые» без ошибки. */
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
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const snippet = text.slice(0, 200).replace(/\s+/g, " ").trim();
    const proxyHint =
      "Если это не ваш случай: откройте админку через `npm run dev` в admin/ (прокси /api → :8000) " +
      "или соберите с `VITE_BACKEND_ORIGIN` на URL API.";
    if (res.status >= 500 && res.status < 600 && (ct.includes("text/plain") || !ct)) {
      throw new Error(
        `Сервер API вернул ошибку HTTP ${res.status} (тело не JSON, часто падение в uvicorn). ` +
          `Смотрите лог бэкенда: scripts/logs-backend.txt или консоль uvicorn. ` +
          (snippet ? `Фрагмент ответа: ${snippet}` : ""),
      );
    }
    if (ct.includes("text/html")) {
      throw new Error(
        `Ответ HTML вместо JSON (HTTP ${res.status}) — запрос, скорее всего, не дошёл до FastAPI. ${proxyHint}`,
      );
    }
    throw new Error(
      `Ответ не JSON (HTTP ${res.status}${ct ? `, ${ct}` : ""}). ${proxyHint}` +
        (snippet ? ` Фрагмент: ${snippet}` : ""),
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

/** Токен есть и не просрочен; просроченный сбрасывает сессию. */
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

export function setSession(token, role) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
  if (role) localStorage.setItem(ROLE_KEY, role);
  else localStorage.removeItem(ROLE_KEY);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

function detail(data, fallback) {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("\n");
  return fallback;
}

/** Ошибка HTTP с кодом — для обработки 409 (конфликт версии) и т.д. */
export function httpError(message, status) {
  const e = new Error(message);
  e.status = status;
  return e;
}

function headersJson() {
  const h = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
}

export async function loginSuperuser(username, password) {
  const res = await fetch(apiUrl("/auth/admin/superuser"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function loginWorker(phone, pin) {
  const res = await fetch(apiUrl("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, pin }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (data.role !== "worker") {
    throw new Error("Этот вход только для сотрудников (роль worker).");
  }
  return data;
}

export async function fetchStats() {
  const res = await fetch(apiUrl("/admin/stats"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchCampaigns() {
  const res = await fetch(apiUrl("/admin/campaigns"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchAttributionDebug({ limit = 25 } = {}) {
  const q = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(`${apiUrl("/admin/campaigns/attribution-debug")}?${q}`, {
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function createCampaign({ name, slug, path }) {
  const res = await fetch(apiUrl("/admin/campaigns"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ name, slug: slug || null, path: path || "/" }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchFeedSettings() {
  const res = await fetch(apiUrl("/admin/feed-settings"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function patchFeedSettings(body) {
  const res = await fetch(apiUrl("/admin/feed-settings"), {
    method: "PATCH",
    headers: headersJson(),
    body: JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchPhotos({
  skip = 0,
  limit = 48,
  gender,
  activeOnly,
  taggingDoneOnly,
  brandId,
  noReactionsOnly,
  sort,
} = {}) {
  const q = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (gender) q.set("gender", gender);
  if (activeOnly) q.set("active_only", "true");
  if (taggingDoneOnly) q.set("tagging_done_only", "true");
  if (brandId) q.set("brand_id", brandId);
  if (noReactionsOnly) q.set("no_reactions_only", "true");
  if (sort && sort !== "recent") q.set("sort", sort);
  const res = await fetch(`${apiUrl("/admin/photos")}?${q}`, { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.items)) {
    throw new Error("Неверный ответ API (нет списка фото). Проверьте VITE_BACKEND_ORIGIN и что бэкенд доступен.");
  }
  return data;
}

/** Все id фото по тем же фильтрам, что fetchPhotos (постранично, limit до 200). */
export async function fetchAllPhotoIds({
  gender,
  activeOnly,
  taggingDoneOnly,
  brandId,
  noReactionsOnly,
  sort,
} = {}) {
  const pageSize = 200;
  const ids = [];
  let skip = 0;
  let total = 0;
  for (;;) {
    const data = await fetchPhotos({
      skip,
      limit: pageSize,
      gender,
      activeOnly,
      taggingDoneOnly,
      brandId,
      noReactionsOnly,
      sort,
    });
    total = data.total ?? 0;
    for (const item of data.items || []) {
      if (item.id) ids.push(item.id);
    }
    skip += pageSize;
    if (skip >= total || !(data.items?.length)) break;
  }
  return { ids, total };
}

export async function fetchAdminPhoto(photoId) {
  const res = await fetch(apiUrl(`/admin/photos/${photoId}`), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw httpError(detail(data, res.statusText), res.status);
  return data;
}

export async function syncPhotosFromObjectStorage(opts = {}) {
  const purge = !!opts.purge;
  const qs = purge ? "?purge=true" : "";
  const res = await fetch(apiUrl(`/admin/photos/sync-object-storage${qs}`), {
    method: "POST",
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchTags() {
  const res = await fetch(apiUrl("/admin/tags"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function createTag(name, { groupId, type } = {}) {
  const body = { name };
  if (groupId) body.group_id = groupId;
  else if (type) body.type = type;
  const res = await fetch(apiUrl("/admin/tags"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchTagGroups() {
  const res = await fetch(apiUrl("/admin/tag-groups"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function createTagGroup({ slug, title, maxTags = 99, minTags = 0 }) {
  const res = await fetch(apiUrl("/admin/tag-groups"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({
      slug,
      title,
      max_tags: maxTags,
      min_tags: minTags,
    }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function updateTagGroup(groupId, patch) {
  const res = await fetch(apiUrl(`/admin/tag-groups/${groupId}`), {
    method: "PATCH",
    headers: headersJson(),
    body: JSON.stringify(patch),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function deleteTagGroup(groupId) {
  const res = await fetch(apiUrl(`/admin/tag-groups/${groupId}`), {
    method: "DELETE",
    headers: headersJson(),
  });
  if (!res.ok) {
    const data = await parseResponseJson(res);
    throw new Error(detail(data, res.statusText));
  }
}

export async function deleteTag(tagId) {
  const res = await fetch(apiUrl(`/admin/tags/${tagId}`), {
    method: "DELETE",
    headers: headersJson(),
  });
  if (!res.ok) {
    const data = await parseResponseJson(res);
    throw new Error(detail(data, res.statusText));
  }
}

export async function updateTag(tagId, name) {
  const res = await fetch(apiUrl(`/admin/tags/${tagId}`), {
    method: "PATCH",
    headers: headersJson(),
    body: JSON.stringify({ name }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function bulkDeletePhotos(photoIds) {
  const res = await fetch(apiUrl("/admin/photos/bulk-delete"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

/** Принимает массив тегов или полное тело с полями разметки. */
/** Эксперимент Ximilar: предложить теги (не сохраняет в БД). Удалить вместе с experimental/ximilar. */
export async function suggestXimilarTags(photoId) {
  const res = await fetch(
    apiUrl(`/admin/experimental/ximilar/photos/${photoId}/suggest-tags`),
    {
      method: "POST",
      headers: headersJson(),
    },
  );
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function putPhotoTags(photoId, tagsOrBody) {
  const body = Array.isArray(tagsOrBody)
    ? { tags: tagsOrBody }
    : {
        tags: tagsOrBody.tags ?? [],
        worker_signal_love: tagsOrBody.worker_signal_love ?? null,
        worker_signal_hit: tagsOrBody.worker_signal_hit ?? null,
        worker_signal_hard: tagsOrBody.worker_signal_hard ?? null,
      };
  if (!Array.isArray(tagsOrBody) && tagsOrBody.apply_brand) {
    body.apply_brand = true;
    body.brand_id = tagsOrBody.brand_id ?? null;
  }
  if (!Array.isArray(tagsOrBody) && Object.prototype.hasOwnProperty.call(tagsOrBody, "moy_sklad_id")) {
    body.moy_sklad_id = tagsOrBody.moy_sklad_id;
  }
  if (!Array.isArray(tagsOrBody) && Object.prototype.hasOwnProperty.call(tagsOrBody, "show_badge")) {
    body.show_badge = !!tagsOrBody.show_badge;
  }
  if (
    !Array.isArray(tagsOrBody) &&
    Object.prototype.hasOwnProperty.call(tagsOrBody, "tagging_review_done")
  ) {
    body.tagging_review_done = !!tagsOrBody.tagging_review_done;
  }
  if (
    !Array.isArray(tagsOrBody) &&
    Object.prototype.hasOwnProperty.call(tagsOrBody, "expected_tags_version")
  ) {
    body.expected_tags_version = tagsOrBody.expected_tags_version;
  }
  const res = await fetch(apiUrl(`/admin/photos/${photoId}/tags`), {
    method: "PUT",
    headers: headersJson(),
    body: JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw httpError(detail(data, res.statusText), res.status);
  return data;
}

export async function fetchTagCatalog() {
  const res = await fetch(apiUrl("/admin/tag/catalog"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.groups) && !Array.isArray(data.sections)) {
    throw new Error("Неверный ответ каталога тегов.");
  }
  return data;
}

export async function createTagInGroup(groupId, name) {
  const res = await fetch(apiUrl(`/admin/tag-groups/${groupId}/tags`), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ name }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchTaggingQueue({ skip = 0, limit = 30 } = {}) {
  const q = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  const res = await fetch(`${apiUrl("/admin/tagging-queue")}?${q}`, { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.items)) {
    throw new Error("Неверный ответ API (нет очереди разметки). Проверьте VITE_BACKEND_ORIGIN и что бэкенд доступен.");
  }
  return data;
}

export async function acquireNextTaggingPhoto() {
  const res = await fetch(apiUrl("/admin/tagging-queue/acquire-next"), {
    method: "POST",
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function claimTaggingPhoto(photoId) {
  const res = await fetch(apiUrl(`/admin/tagging-queue/${photoId}/claim`), {
    method: "POST",
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function releaseTaggingPhoto(photoId) {
  const res = await fetch(apiUrl(`/admin/tagging-queue/${photoId}/release`), {
    method: "POST",
    headers: headersJson(),
  });
  if (!res.ok) {
    const data = await parseResponseJson(res);
    throw new Error(detail(data, res.statusText));
  }
}

export async function fetchUsers({ skip = 0, limit = 50 } = {}) {
  const q = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  const res = await fetch(`${apiUrl("/admin/users")}?${q}`, { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchUserDetail(userId) {
  const res = await fetch(apiUrl(`/admin/users/${userId}/detail`), {
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function createUser({ phone, pin, role }) {
  const res = await fetch(apiUrl("/admin/users"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ phone, pin, role }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

/** Поля опциональны; передайте только то, что меняется. */
export async function updateUser(userId, body) {
  const res = await fetch(apiUrl(`/admin/users/${userId}`), {
    method: "PATCH",
    headers: headersJson(),
    body: JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function deleteUser(userId) {
  const res = await fetch(apiUrl(`/admin/users/${userId}`), {
    method: "DELETE",
    headers: headersJson(),
  });
  if (res.ok) {
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (ct.includes("text/html")) {
      throw new Error(
        "DELETE вернул HTML вместо пустого ответа API — запрос не дошёл до FastAPI. " +
          "Запустите `npm run dev` в admin/ (прокси /api) или задайте VITE_BACKEND_ORIGIN.",
      );
    }
    return;
  }
  const data = await parseResponseJson(res);
  throw new Error(detail(data, res.statusText));
}

function headersAuthOnly() {
  const h = {};
  const t = getToken();
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
}

export async function fetchBrands() {
  const res = await fetch(apiUrl("/admin/brands"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.items)) {
    throw new Error("Неверный ответ API (список брендов).");
  }
  return data;
}

export async function createBrand(name) {
  const res = await fetch(apiUrl("/admin/brands"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ name }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchFittingRequests({ skip = 0, limit = 50 } = {}) {
  const q = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  const res = await fetch(`${apiUrl("/admin/fitting-requests")}?${q}`, { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.items)) {
    throw new Error("Неверный ответ API (список заявок на примерку).");
  }
  return data;
}

export async function fetchAiIngestLimits() {
  const res = await fetch(apiUrl("/admin/ai-ingest/limits"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchAiIngestStats() {
  const res = await fetch(apiUrl("/admin/ai-ingest/stats"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function fetchAiIngestJobs({ skip = 0, limit = 50 } = {}) {
  const q = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  const res = await fetch(`${apiUrl("/admin/ai-ingest/jobs")}?${q}`, { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.items)) {
    throw new Error("Неверный ответ API (список задач).");
  }
  return data;
}

export async function uploadAiIngestBatch(
  gender,
  brandId,
  fileList,
  { showBadge = false, sourceMode = "flatlay" } = {},
) {
  const fd = new FormData();
  fd.append("gender", gender);
  fd.append("brand_id", brandId);
  fd.append("source_mode", sourceMode);
  fd.append("show_badge", showBadge ? "true" : "false");
  for (const f of fileList) {
    fd.append("files", f);
  }
  const res = await fetch(apiUrl("/admin/ai-ingest/upload"), {
    method: "POST",
    headers: headersAuthOnly(),
    body: fd,
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function retryAiIngestJob(jobId) {
  const res = await fetch(apiUrl(`/admin/ai-ingest/jobs/${jobId}/retry`), {
    method: "POST",
    headers: headersJson(),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function deleteAiIngestJob(jobId) {
  const res = await fetch(apiUrl(`/admin/ai-ingest/jobs/${jobId}`), {
    method: "DELETE",
    headers: headersJson(),
  });
  if (!res.ok) {
    const data = await parseResponseJson(res);
    throw new Error(detail(data, res.statusText));
  }
}

export async function fetchPromoBanners() {
  const res = await fetch(apiUrl("/admin/promo-banners"), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function createPromoBanner(body) {
  const res = await fetch(apiUrl("/admin/promo-banners"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function updatePromoBanner(id, body) {
  const res = await fetch(apiUrl(`/admin/promo-banners/${id}`), {
    method: "PATCH",
    headers: headersJson(),
    body: JSON.stringify(body),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}

export async function deletePromoBanner(id) {
  const res = await fetch(apiUrl(`/admin/promo-banners/${id}`), {
    method: "DELETE",
    headers: headersJson(),
  });
  if (!res.ok && res.status !== 204) {
    const data = await parseResponseJson(res);
    throw new Error(detail(data, res.statusText));
  }
}

export async function uploadPromoBannerImage(id, file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(apiUrl(`/admin/promo-banners/${id}/image`), {
    method: "POST",
    headers: headersAuthOnly(),
    body: fd,
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
}
