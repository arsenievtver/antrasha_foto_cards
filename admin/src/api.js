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

export async function fetchPhotos({ skip = 0, limit = 48, gender, activeOnly, taggingDoneOnly, brandId } = {}) {
  const q = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (gender) q.set("gender", gender);
  if (activeOnly) q.set("active_only", "true");
  if (taggingDoneOnly) q.set("tagging_done_only", "true");
  if (brandId) q.set("brand_id", brandId);
  const res = await fetch(`${apiUrl("/admin/photos")}?${q}`, { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  if (!Array.isArray(data.items)) {
    throw new Error("Неверный ответ API (нет списка фото). Проверьте VITE_BACKEND_ORIGIN и что бэкенд доступен.");
  }
  return data;
}

export async function fetchAdminPhoto(photoId) {
  const res = await fetch(apiUrl(`/admin/photos/${photoId}`), { headers: headersJson() });
  const data = await parseResponseJson(res);
  if (!res.ok) throw httpError(detail(data, res.statusText), res.status);
  return data;
}

export async function syncPhotosFromObjectStorage() {
  const res = await fetch(apiUrl("/admin/photos/sync-object-storage"), {
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

export async function createTag(name, type) {
  const res = await fetch(apiUrl("/admin/tags"), {
    method: "POST",
    headers: headersJson(),
    body: JSON.stringify({ name, type }),
  });
  const data = await parseResponseJson(res);
  if (!res.ok) throw new Error(detail(data, res.statusText));
  return data;
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
  if (!Array.isArray(data.sections)) {
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

export async function uploadAiIngestBatch(gender, brandId, fileList) {
  const fd = new FormData();
  fd.append("gender", gender);
  fd.append("brand_id", brandId);
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
