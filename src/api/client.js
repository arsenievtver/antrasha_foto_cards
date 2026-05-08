const SESSION_KEY = "antrasha_session_id";
const AUTH_KEY = "antrasha_access_token";

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

/** Создаёт сессию один раз и кеширует ID в localStorage */
export async function ensureSessionId() {
	let id = localStorage.getItem(SESSION_KEY);
	if (id) return id;
	const res = await fetch(apiUrl("/sessions"), { method: "POST" });
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
	return id;
}

/** Новая анонимная сессия (если старая на сервере отсутствует — см. registerUser). */
export async function createFreshSessionId() {
	const res = await fetch(apiUrl("/sessions"), { method: "POST" });
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

export function setAuthToken(token) {
	if (token) localStorage.setItem(AUTH_KEY, token);
	else localStorage.removeItem(AUTH_KEY);
}

export async function loadFeed(gender, { limit = 30 } = {}) {
	await ensureSessionId();
	const headers = { "X-Session-Id": localStorage.getItem(SESSION_KEY) };
	const t = getAuthToken();
	if (t) headers.Authorization = `Bearer ${t}`;
	const q = new URLSearchParams({ gender, limit: String(limit) });
	const res = await fetch(`${apiUrl("/feed")}?${q}`, { headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Feed ${res.status}`);
	}
	return res.json();
}

export async function fetchMe() {
	const t = getAuthToken();
	if (!t) return null;
	const res = await fetch(apiUrl("/auth/me"), {
		headers: { Authorization: `Bearer ${t}` },
	});
	if (res.status === 401) return null;
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
	setAuthToken(data.access_token);
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
