import { getStoredRef } from "../utils/attribution.js";

const SESSION_KEY = "antrasha_session_id";
const REF_BOUND_SESSION_KEY = "antrasha_ref_bound_session";
const AUTH_KEY = "antrasha_access_token";
const REFRESH_KEY = "antrasha_refresh_token";
export const REMEMBER_PHONE_KEY = "antrasha_remember_phone";

let refreshInFlight = null;

/**
 * Прямой URL бэкенда без `/api`, например http://127.0.0.1:8000
 * (удобно для preview/production без reverse-proxy).
 * Если не задан — относительные пути `/api/...` (dev-сервер и preview с proxy из vite.config).
 */
const BACKEND_ORIGIN = (import.meta.env.VITE_API_BASE || "")
	.replace(/\/$/, "");

/**
 * Путь к эндпоинту: `/sessions`, `/auth/register`.
 */
export function apiUrl(path) {
	const p = path.startsWith("/") ? path : `/${path}`;
	if (BACKEND_ORIGIN) return `${BACKEND_ORIGIN}${p}`;
	return `/api${p}`;
}

function parseErrorPayload(data, fallback) {
	const d = data?.detail;
	if (typeof d === "string") return d;
	if (Array.isArray(d))
		return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
	return fallback;
}

async function postSession() {
	const ref = getStoredRef();
	const res = await fetch(apiUrl("/sessions"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(ref ? { ref } : {}),
	});
	return res;
}

/** Привязать ?ref= к уже существующей сессии (если кампания ещё не была задана). */
async function bindSessionAttribution(sessionId, ref) {
	const res = await fetch(apiUrl(`/sessions/${sessionId}/attribution`), {
		method: "PATCH",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ ref }),
	});
	return res;
}

async function tryBindRefToExistingSession(sessionId) {
	const ref = getStoredRef();
	if (!ref || localStorage.getItem(REF_BOUND_SESSION_KEY) === sessionId) {
		return;
	}
	try {
		const res = await bindSessionAttribution(sessionId, ref);
		if (res.ok) {
			localStorage.setItem(REF_BOUND_SESSION_KEY, sessionId);
		}
	} catch {
		/* сеть — не блокируем приложение */
	}
}

/** Создаёт сессию один раз и кеширует ID в localStorage */
export async function ensureSessionId() {
	let id = localStorage.getItem(SESSION_KEY);
	if (id) {
		await tryBindRefToExistingSession(id);
		return id;
	}
	const ref = getStoredRef();
	const res = await postSession();
	if (!res.ok) {
		const raw = await res.text();
		let data = {};
		try {
			data = JSON.parse(raw);
		} catch {
			/* empty */
		}
		throw new Error(
			parseErrorPayload(data, raw || `Session failed: ${res.status}`),
		);
	}
	const data = await res.json();
	id = data.session_id;
	localStorage.setItem(SESSION_KEY, id);
	if (ref) {
		localStorage.setItem(REF_BOUND_SESSION_KEY, id);
	}
	return id;
}

/** Новая анонимная сессия (если старая на сервере отсутствует — см. registerUser). */
export async function createFreshSessionId() {
	const res = await postSession();
	if (!res.ok) {
		throw new Error(`Session failed: ${res.status}`);
	}
	const data = await res.json();
	const id = data.session_id;
	localStorage.setItem(SESSION_KEY, id);
	return id;
}

export function getAuthToken() {
	return localStorage.getItem(AUTH_KEY);
}

export function getRefreshToken() {
	return localStorage.getItem(REFRESH_KEY);
}

export function setAuthToken(token, refreshToken = undefined) {
	if (token) localStorage.setItem(AUTH_KEY, token);
	else localStorage.removeItem(AUTH_KEY);
	if (refreshToken !== undefined) {
		if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
		else localStorage.removeItem(REFRESH_KEY);
	}
}

export function clearAuthTokens() {
	localStorage.removeItem(AUTH_KEY);
	localStorage.removeItem(REFRESH_KEY);
}

export function getRememberedPhone() {
	return localStorage.getItem(REMEMBER_PHONE_KEY) || "";
}

export function setRememberedPhone(phone) {
	if (phone) localStorage.setItem(REMEMBER_PHONE_KEY, phone);
	else localStorage.removeItem(REMEMBER_PHONE_KEY);
}

/** Обновляет access (и refresh при ротации) по refresh JWT. */
export async function refreshAccessToken() {
	const refresh = getRefreshToken();
	if (!refresh) return false;
	if (!refreshInFlight) {
		refreshInFlight = (async () => {
			try {
				const res = await fetch(apiUrl("/auth/refresh"), {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ refresh_token: refresh }),
				});
				const data = await res.json().catch(() => ({}));
				if (!res.ok) return false;
				setAuthToken(data.access_token, data.refresh_token ?? refresh);
				return true;
			} finally {
				refreshInFlight = null;
			}
		})();
	}
	return refreshInFlight;
}

function storeLoginTokens(data) {
	setAuthToken(data.access_token, data.refresh_token ?? null);
}

async function sessionAuthHeaders() {
	await ensureSessionId();
	const headers = { "X-Session-Id": localStorage.getItem(SESSION_KEY) };
	const t = getAuthToken();
	if (t) headers.Authorization = `Bearer ${t}`;
	return headers;
}

export async function fetchActivePromoBanner() {
	const headers = await sessionAuthHeaders();
	const res = await fetch(apiUrl("/promo-banners/active"), { headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `promo-banners ${res.status}`);
	}
	return res.json();
}

export async function markPromoBannerSeen(bannerId) {
	const headers = await sessionAuthHeaders();
	const res = await fetch(apiUrl(`/promo-banners/${bannerId}/seen`), {
		method: "POST",
		headers,
	});
	if (!res.ok && res.status !== 204) {
		const text = await res.text();
		throw new Error(text || `promo seen ${res.status}`);
	}
}

export async function loadFeed(gender, { limit = 30 } = {}) {
	const headers = await sessionAuthHeaders();
	const q = new URLSearchParams({ gender, limit: String(limit) });
	const res = await fetch(`${apiUrl("/feed")}?${q}`, { headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Feed ${res.status}`);
	}
	return res.json();
}

export async function fetchMe({ retryOn401 = true } = {}) {
	const t = getAuthToken();
	if (!t) return null;
	const res = await fetch(apiUrl("/auth/me"), {
		headers: { Authorization: `Bearer ${t}` },
	});
	if (res.status === 401) {
		if (retryOn401 && (await refreshAccessToken())) {
			return fetchMe({ retryOn401: false });
		}
		return null;
	}
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `me ${res.status}`);
	}
	return res.json();
}

export async function loginUser({ phone, pin }) {
	const res = await fetch(apiUrl("/auth/login"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ phone, pin }),
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		throw new Error(
			parseErrorPayload(data, `Вход не удался (${res.status})`),
		);
	}
	storeLoginTokens(data);
	return data;
}

async function postRegister(body) {
	const res = await fetch(apiUrl("/auth/register"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		const msg = parseErrorPayload(
			data,
			res.status === 404
				? "Сервер не нашёл маршрут или сессию. Проверьте, что UI открыт через dev/preview с proxy или задайте VITE_API_BASE на URL API."
				: `Регистрация не удалась (${res.status})`,
		);
		throw new Error(msg);
	}
	return data;
}

export async function registerUser({ displayName, phone, pin }) {
	await ensureSessionId();
	let session_id = localStorage.getItem(SESSION_KEY);
	try {
		return await postRegister({
			display_name: displayName.trim(),
			phone,
			pin,
			session_id,
		});
	} catch (e) {
		const text = e.message || "";
		const sessionMissing = text.includes("Session not found");
		if (sessionMissing) {
			await createFreshSessionId();
			session_id = localStorage.getItem(SESSION_KEY);
			return await postRegister({
				display_name: displayName.trim(),
				phone,
				pin,
				session_id,
			});
		}
		throw e;
	}
}

export async function createFittingRequest({ likes, total, note, photoIds } = {}) {
	const t = getAuthToken();
	if (!t) throw new Error("Нужно войти в профиль");
	const res = await fetch(apiUrl("/auth/fitting-request"), {
		method: "POST",
		headers: {
			Authorization: `Bearer ${t}`,
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			likes: Number(likes) || 0,
			total: Number(total) || 0,
			photo_ids: Array.isArray(photoIds) ? photoIds : [],
			note: note ?? null,
		}),
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		throw new Error(
			parseErrorPayload(data, `Не удалось отправить заявку (${res.status})`),
		);
	}
	return data;
}

/** Заявка на примерку без аккаунта (страница «О бренде» и т.п.) */
export async function createGuestFittingRequest({ phone, note } = {}) {
	const res = await fetch(apiUrl("/guest/fitting-request"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			phone: phone ?? "",
			note: note ?? null,
		}),
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		throw new Error(
			parseErrorPayload(data, `Не удалось отправить заявку (${res.status})`),
		);
	}
	return data;
}

export async function postInteraction({ photoId, action, viewTimeMs }) {
	await ensureSessionId();
	const headers = {
		"X-Session-Id": localStorage.getItem(SESSION_KEY),
		"Content-Type": "application/json",
	};
	const t = getAuthToken();
	if (t) headers.Authorization = `Bearer ${t}`;
	const res = await fetch(apiUrl("/interactions"), {
		method: "POST",
		headers,
		body: JSON.stringify({
			photo_id: photoId,
			action,
			view_time_ms: viewTimeMs ?? null,
		}),
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Interaction ${res.status}`);
	}
	return res.json();
}
