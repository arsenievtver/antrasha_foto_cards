import { apiUrl, ensureSessionId, getAuthToken } from "../api/client.js";

export const PUSH_PROMPT_DISMISSED_KEY = "antrasha_push_prompt_dismissed";
export const PUSH_SUBSCRIBED_KEY = "antrasha_push_subscribed";

const SW_URL = "/sw.js";
const SW_SCOPE = "/";
const SW_READY_MS = 25000;

let swPreparePromise = null;

export function isStandaloneDisplayMode() {
	if (typeof window === "undefined") return false;
	if (window.navigator.standalone === true) return true;
	for (const mode of ["standalone", "fullscreen", "minimal-ui"]) {
		if (window.matchMedia(`(display-mode: ${mode})`).matches) return true;
	}
	return false;
}

function isIosSafari() {
	if (typeof navigator === "undefined") return false;
	return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

function waitForWorkerState(worker, state, timeoutMs) {
	return new Promise((resolve, reject) => {
		if (!worker) {
			reject(new Error("нет worker"));
			return;
		}
		if (worker.state === state) {
			resolve();
			return;
		}
		const timer = window.setTimeout(() => {
			worker.removeEventListener("statechange", onChange);
			reject(new Error(`worker не перешёл в ${state}`));
		}, timeoutMs);
		function onChange() {
			if (worker.state === state) {
				window.clearTimeout(timer);
				worker.removeEventListener("statechange", onChange);
				resolve();
			}
		}
		worker.addEventListener("statechange", onChange);
	});
}

async function waitForActiveRegistration(reg, timeoutMs = SW_READY_MS) {
	if (!reg) return null;
	if (reg.active) return reg;
	const pending = reg.installing || reg.waiting;
	if (pending) {
		await waitForWorkerState(pending, "activated", timeoutMs);
	}
	return (await navigator.serviceWorker.getRegistration(SW_SCOPE)) || reg;
}

function probeHasPushManager(probe, reg) {
	if (probe.pushManagerApi) return true;
	return Boolean(reg?.pushManager);
}

/**
 * @typedef {Object} PushEnvironmentProbe
 * @property {boolean} secure
 * @property {boolean} serviceWorkerApi
 * @property {boolean} pushManagerApi
 * @property {boolean} standalone
 * @property {boolean} registrationReady
 * @property {string} [registerError]
 */

/** Регистрация SW + ожидание active (iOS PWA). */
export async function preparePushServiceWorker({ forceRetry = false } = {}) {
	if (forceRetry) swPreparePromise = null;

	if (!swPreparePromise) {
		swPreparePromise = (async () => {
			/** @type {PushEnvironmentProbe} */
			const probe = {
				secure: typeof window !== "undefined" && window.isSecureContext,
				serviceWorkerApi:
					typeof navigator !== "undefined" && "serviceWorker" in navigator,
				pushManagerApi: typeof window !== "undefined" && "PushManager" in window,
				standalone: isStandaloneDisplayMode(),
				registrationReady: false,
			};

			if (!probe.secure || !probe.serviceWorkerApi) {
				return probe;
			}

			try {
				let reg = await navigator.serviceWorker.getRegistration(SW_SCOPE);
				if (!reg || forceRetry) {
					if (forceRetry) {
						const all = await navigator.serviceWorker.getRegistrations();
						await Promise.all(all.map((r) => r.unregister()));
					}
					reg = await navigator.serviceWorker.register(SW_URL, {
						scope: SW_SCOPE,
						updateViaCache: "none",
					});
				} else {
					await reg.update().catch(() => {});
				}

				await Promise.race([
					navigator.serviceWorker.ready,
					new Promise((_, reject) => {
						window.setTimeout(
							() => reject(new Error("service worker не активировался вовремя")),
							SW_READY_MS,
						);
					}),
				]);

				reg = (await waitForActiveRegistration(reg)) || reg;
				probe.pushManagerApi = probeHasPushManager(probe, reg);
				probe.registrationReady = Boolean(reg?.active);
			} catch (e) {
				probe.registerError = e?.message || String(e);
			}

			return probe;
		})().finally(() => {
			swPreparePromise = null;
		});
	}

	return swPreparePromise;
}

/** Почему push недоступен — для текста в UI. */
export function getPushUnsupportedHint(probe = null) {
	if (typeof window === "undefined") return "Push недоступен в этом окружении.";
	if (!window.isSecureContext) {
		return "Нужно HTTPS. Откройте https://antrasha.ru и обновите страницу.";
	}

	const ios = isIosSafari();
	const standalone = probe?.standalone ?? isStandaloneDisplayMode();
	const swApi = probe?.serviceWorkerApi ?? "serviceWorker" in navigator;
	const pushApi = probe?.pushManagerApi ?? "PushManager" in window;

	// Во вкладке Safari на iPhone нет PushManager и часто нет SW — это норма, не «старый iOS».
	if (ios && !standalone) {
		return "На iPhone push включаются только в приложении ANTRASHA с «Домашнего экрана»: откройте иконку (не Safari). Если иконка уже есть — полностью закройте Safari и запускайте только с экрана «Домой».";
	}

	if (ios && standalone && !swApi) {
		return "В установленном приложении не доступен service worker. Удалите ярлык ANTRASHA, добавьте заново (Поделиться → «На экран Домой», «Открыть как веб-приложение») и откройте с иконки.";
	}

	if (probe?.registerError) {
		return `Service worker не запустился: ${probe.registerError}. Нажмите «Повторить» ниже или удалите ярлык и установите PWA заново — после неудачного обновления сайта на iPhone такое бывает.`;
	}

	if (probe && swApi && !probe.registrationReady) {
		return "Service worker ещё загружается. Подождите 3–5 секунд и нажмите «Повторить».";
	}

	if (ios && standalone && !pushApi) {
		return "Push API недоступен в этом приложении. Обновите iOS до последней версии, перезапустите iPhone и снова откройте ANTRASHA с иконки.";
	}

	if (!swApi || !pushApi) {
		return "Этот браузер не поддерживает web push.";
	}

	return "Push-уведомления недоступны в этом режиме.";
}

export function isPushReadyFromProbe(probe) {
	if (!probe?.secure || !probe.serviceWorkerApi) return false;
	if (!probe.registrationReady) return false;
	if (!probe.pushManagerApi) return false;
	if (isIosSafari() && !probe.standalone) return false;
	return true;
}

/** Быстрая проверка без ожидания SW. */
export function isPushSupported() {
	if (typeof window === "undefined") return false;
	if (!window.isSecureContext) return false;
	if (isIosSafari() && !isStandaloneDisplayMode()) return false;
	return "serviceWorker" in navigator && "PushManager" in window;
}

export function isPushSubscribedLocally() {
	try {
		return localStorage.getItem(PUSH_SUBSCRIBED_KEY) === "1";
	} catch {
		return false;
	}
}

export function isPushPromptDismissed() {
	try {
		return localStorage.getItem(PUSH_PROMPT_DISMISSED_KEY) === "1";
	} catch {
		return true;
	}
}

export function markPushPromptDismissed() {
	try {
		localStorage.setItem(PUSH_PROMPT_DISMISSED_KEY, "1");
	} catch {
		/* ignore */
	}
}

export function markPushSubscribedLocally() {
	try {
		localStorage.setItem(PUSH_SUBSCRIBED_KEY, "1");
	} catch {
		/* ignore */
	}
}

export function clearPushSubscribedLocally() {
	try {
		localStorage.removeItem(PUSH_SUBSCRIBED_KEY);
	} catch {
		/* ignore */
	}
}

const GENDER_SCOPE_LABELS = {
	male: "мужские новинки",
	female: "женские новинки",
	both: "мужские и женские новинки",
};

export function pushGenderScopeLabel(scope) {
	return GENDER_SCOPE_LABELS[scope] || GENDER_SCOPE_LABELS.both;
}

async function pushAuthHeaders() {
	await ensureSessionId();
	const headers = {
		"Content-Type": "application/json",
		"X-Session-Id": localStorage.getItem("antrasha_session_id"),
	};
	const token = getAuthToken();
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

async function getServiceWorkerRegistrationForPush() {
	const probe = await preparePushServiceWorker();
	if (!isPushReadyFromProbe(probe)) {
		throw new Error(getPushUnsupportedHint(probe));
	}
	return navigator.serviceWorker.ready;
}

/** Подписка в браузере на этом устройстве. */
export async function getBrowserPushSubscription() {
	try {
		const registration = await getServiceWorkerRegistrationForPush();
		return registration.pushManager.getSubscription();
	} catch {
		return null;
	}
}

export async function isPushActiveOnDevice() {
	const sub = await getBrowserPushSubscription();
	return Boolean(sub) || isPushSubscribedLocally();
}

/** Статус в профиле (только для авторизованных). */
export async function fetchPushAccountStatus() {
	if (!getAuthToken()) return null;
	const res = await fetch(apiUrl("/push/account-status"), {
		headers: await pushAuthHeaders(),
	});
	if (res.status === 401) return null;
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `push account-status ${res.status}`);
	}
	return res.json();
}

async function postPushUnsubscribe(endpoint) {
	const res = await fetch(apiUrl("/push/unsubscribe"), {
		method: "POST",
		headers: await pushAuthHeaders(),
		body: JSON.stringify({ endpoint }),
	});
	if (!res.ok && res.status !== 204) {
		const text = await res.text();
		throw new Error(text || `unsubscribe ${res.status}`);
	}
}

async function postPushUnsubscribeAll() {
	const res = await fetch(apiUrl("/push/unsubscribe-all"), {
		method: "POST",
		headers: await pushAuthHeaders(),
	});
	if (!res.ok && res.status !== 204) {
		const text = await res.text();
		throw new Error(text || `unsubscribe-all ${res.status}`);
	}
}

function urlBase64ToUint8Array(base64String) {
	const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
	const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
	const raw = atob(base64);
	const out = new Uint8Array(raw.length);
	for (let i = 0; i < raw.length; i += 1) {
		out[i] = raw.charCodeAt(i);
	}
	return out;
}

async function fetchVapidPublicKey() {
	const res = await fetch(apiUrl("/push/vapid-public-key"));
	if (res.status === 503) return null;
	if (!res.ok) {
		throw new Error(`VAPID key ${res.status}`);
	}
	const data = await res.json();
	return data.public_key;
}

async function postPushSubscription(subscription, genderScope) {
	const json = subscription.toJSON();
	const res = await fetch(apiUrl("/push/subscribe"), {
		method: "POST",
		headers: await pushAuthHeaders(),
		body: JSON.stringify({
			endpoint: json.endpoint,
			keys: json.keys,
			gender_scope: genderScope,
		}),
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `subscribe ${res.status}`);
	}
}

export async function isPushAvailableOnServer() {
	try {
		const key = await fetchVapidPublicKey();
		return Boolean(key);
	} catch {
		return false;
	}
}

export async function subscribeToNewPhotosPush(genderScope = "both") {
	const probe = await preparePushServiceWorker();
	if (!isPushReadyFromProbe(probe)) {
		throw new Error(getPushUnsupportedHint(probe));
	}
	const scope =
		genderScope === "male" || genderScope === "female" || genderScope === "both"
			? genderScope
			: "both";

	let permission = "default";
	if ("Notification" in window) {
		permission = await Notification.requestPermission();
	} else if (isIosSafari() && isStandaloneDisplayMode()) {
		permission = "default";
	} else {
		throw new Error(getPushUnsupportedHint(probe));
	}
	if (permission !== "granted") {
		throw new Error("Разрешение на уведомления не получено");
	}

	const publicKey = await fetchVapidPublicKey();
	if (!publicKey) {
		throw new Error("Уведомления временно недоступны");
	}

	const registration = await getServiceWorkerRegistrationForPush();
	const subscription = await registration.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: urlBase64ToUint8Array(publicKey),
	});

	await postPushSubscription(subscription, scope);
	markPushSubscribedLocally();
	markPushPromptDismissed();
	return subscription;
}

/** Отключить push на этом устройстве; для профиля — снять подписку на сервере. */
export async function unsubscribeFromNewPhotosPush() {
	try {
		const registration = await getServiceWorkerRegistrationForPush();
		const sub = await registration.pushManager.getSubscription();
		if (sub?.endpoint) {
			await postPushUnsubscribe(sub.endpoint);
			try {
				await sub.unsubscribe();
			} catch {
				/* ignore */
			}
		} else if (getAuthToken()) {
			await postPushUnsubscribeAll();
		}
	} catch {
		if (getAuthToken()) {
			await postPushUnsubscribeAll();
		}
	}
	clearPushSubscribedLocally();
}
