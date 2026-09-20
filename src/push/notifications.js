import { apiUrl, ensureSessionId, getAuthToken } from "../api/client.js";

export const PUSH_PROMPT_DISMISSED_KEY = "antrasha_push_prompt_dismissed";
export const PUSH_SUBSCRIBED_KEY = "antrasha_push_subscribed";

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

function isAntrashaPwaLaunchUrl() {
	try {
		return new URL(window.location.href).searchParams.get("pwa") === "antrasha-client";
	} catch {
		return false;
	}
}

/** Синхронная проверка API (без ожидания регистрации SW). */
export function isPushSupported() {
	if (typeof window === "undefined") return false;
	if (!window.isSecureContext) return false;
	if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
		return false;
	}
	return true;
}

/**
 * @typedef {Object} PushEnvironmentProbe
 * @property {boolean} secure
 * @property {boolean} serviceWorkerApi
 * @property {boolean} pushManagerApi
 * @property {boolean} standalone
 * @property {boolean} pwaLaunchUrl
 * @property {boolean} registrationReady
 * @property {string} [registerError]
 */

/** Регистрация SW + ожидание ready (iOS PWA часто не успевает к первому тапу по колокольчику). */
export async function preparePushServiceWorker() {
	/** @type {PushEnvironmentProbe} */
	const probe = {
		secure: typeof window !== "undefined" && window.isSecureContext,
		serviceWorkerApi: typeof navigator !== "undefined" && "serviceWorker" in navigator,
		pushManagerApi: typeof window !== "undefined" && "PushManager" in window,
		standalone: isStandaloneDisplayMode(),
		pwaLaunchUrl: isAntrashaPwaLaunchUrl(),
		registrationReady: false,
	};

	if (!probe.secure || !probe.serviceWorkerApi) {
		return probe;
	}

	try {
		let reg = await navigator.serviceWorker.getRegistration("/");
		if (!reg) {
			reg = await navigator.serviceWorker.register("/sw.js", {
				scope: "/",
				updateViaCache: "none",
			});
		}
		await Promise.race([
			navigator.serviceWorker.ready,
			new Promise((_, reject) => {
				window.setTimeout(
					() => reject(new Error("Service worker не активировался за 15 с")),
					15000,
				);
			}),
		]);
		probe.registrationReady = Boolean(reg?.active || navigator.serviceWorker.controller);
	} catch (e) {
		probe.registerError = e?.message || String(e);
	}

	return probe;
}

/** Почему push недоступен — для текста в UI. */
export function getPushUnsupportedHint(probe = null) {
	if (typeof window === "undefined") return "Push недоступен в этом окружении.";
	if (!window.isSecureContext) {
		return "Нужно защищённое соединение (HTTPS). Откройте https://antrasha.ru и обновите страницу.";
	}

	const ios = isIosSafari();
	const standalone = probe?.standalone ?? isStandaloneDisplayMode();
	const pwaUrl = probe?.pwaLaunchUrl ?? isAntrashaPwaLaunchUrl();
	const swApi = probe?.serviceWorkerApi ?? "serviceWorker" in navigator;
	const pushApi = probe?.pushManagerApi ?? "PushManager" in window;

	if (!pushApi) {
		return "Обновите iOS до 16.4 или новее — без этого push на iPhone недоступны.";
	}

	if (!swApi) {
		if (ios) {
			if (standalone || pwaUrl) {
				return "Service worker не стартовал в приложении с «Домашнего экрана». Полностью закройте ANTRASHA (смахните из переключателя приложений), откройте снова с иконки и повторите. Если не помогло — удалите ярлык и добавьте заново с «Открыть как веб-приложение».";
			}
			return "На iPhone push работают только из иконки ANTRASHA на «Домашнем экране» (не из вкладки Safari). Добавьте через Поделиться → «На экран Домой» с включённым «Открыть как веб-приложение».";
		}
		return "Service worker недоступен в этом браузере.";
	}

	if (probe?.registerError) {
		return `Не удалось запустить service worker: ${probe.registerError}. Закройте приложение полностью и откройте с иконки ANTRASHA ещё раз.`;
	}

	if (probe && swApi && pushApi && !probe.registrationReady) {
		return "Service worker ещё не готов. Подождите пару секунд и нажмите «Уведомления» снова или перезапустите приложение с иконки.";
	}

	if (ios && !standalone && !pwaUrl) {
		return "Откройте ANTRASHA с иконки на «Домашнем экране» (не Safari) — затем включите уведомления.";
	}

	return "Push-уведомления недоступны в этом режиме.";
}

/** Готовность push после попытки регистрации SW. */
export function isPushReadyFromProbe(probe) {
	if (!probe?.secure || !probe.serviceWorkerApi || !probe.pushManagerApi) return false;
	if (!probe.registrationReady) return false;
	if (isIosSafari() && !probe.standalone && !probe.pwaLaunchUrl) return false;
	return true;
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

/** Подписка в браузере на этом устройстве. */
export async function getBrowserPushSubscription() {
	if (!isPushSupported()) return null;
	try {
		const registration = await waitForServiceWorkerRegistration();
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
	if (!isPushSupported()) return false;
	try {
		const key = await fetchVapidPublicKey();
		return Boolean(key);
	} catch {
		return false;
	}
}

async function waitForServiceWorkerRegistration() {
	const probe = await preparePushServiceWorker();
	if (!isPushReadyFromProbe(probe)) {
		throw new Error(getPushUnsupportedHint(probe));
	}
	return navigator.serviceWorker.ready;
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
	} else if (
		isIosSafari() &&
		(isStandaloneDisplayMode() || isAntrashaPwaLaunchUrl())
	) {
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

	const registration = await waitForServiceWorkerRegistration();
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
	if (!isPushSupported()) {
		clearPushSubscribedLocally();
		return;
	}
	const registration = await waitForServiceWorkerRegistration();
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
	clearPushSubscribedLocally();
}
