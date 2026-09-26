import { apiUrl, ensureSessionId, getAuthToken } from "../api/client.js";

export const PUSH_PROMPT_DISMISSED_KEY = "antrasha_push_prompt_dismissed";
export const PUSH_SUBSCRIBED_KEY = "antrasha_push_subscribed";

export function isStandaloneDisplayMode() {
	if (typeof window === "undefined") return false;
	return (
		window.navigator.standalone === true ||
		window.matchMedia("(display-mode: standalone)").matches
	);
}

function isIosSafari() {
	if (typeof navigator === "undefined") return false;
	return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

/** Браузер без Notification API не помечаем: разрешение там запросить нельзя. */
export function isPushPermissionMissing() {
	if (typeof Notification === "undefined") return false;
	return Notification.permission !== "granted";
}

export function isPushSupported() {
	if (typeof window === "undefined") return false;
	if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
		return false;
	}
	if (isIosSafari() && !isStandaloneDisplayMode()) {
		return false;
	}
	return true;
}

export function getPushUnsupportedHint() {
	if (typeof window === "undefined") return "Push недоступен в этом окружении.";
	if (isIosSafari() && !isStandaloneDisplayMode()) {
		return "На iPhone уведомления включаются из иконки ANTRASHA на «Домашнем экране», не из вкладки Safari.";
	}
	if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
		return "Этот браузер не поддерживает push-уведомления.";
	}
	return "Push-уведомления недоступны в этом режиме.";
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

async function getServiceWorkerRegistration() {
	if (!("serviceWorker" in navigator)) {
		throw new Error(getPushUnsupportedHint());
	}
	return navigator.serviceWorker.ready;
}

export async function getBrowserPushSubscription() {
	if (!isPushSupported()) return null;
	try {
		const registration = await getServiceWorkerRegistration();
		return registration.pushManager.getSubscription();
	} catch {
		return null;
	}
}

export async function isPushActiveOnDevice() {
	const sub = await getBrowserPushSubscription();
	return Boolean(sub) || isPushSubscribedLocally();
}

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

export async function subscribeToNewPhotosPush(genderScope = "both") {
	if (!isPushSupported()) {
		throw new Error(getPushUnsupportedHint());
	}
	const scope =
		genderScope === "male" || genderScope === "female" || genderScope === "both"
			? genderScope
			: "both";

	const permission = await Notification.requestPermission();
	if (permission !== "granted") {
		throw new Error("Разрешение на уведомления не получено");
	}

	const publicKey = await fetchVapidPublicKey();
	if (!publicKey) {
		throw new Error("Уведомления временно недоступны");
	}

	const registration = await getServiceWorkerRegistration();
	const subscription = await registration.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: urlBase64ToUint8Array(publicKey),
	});

	await postPushSubscription(subscription, scope);
	markPushSubscribedLocally();
	markPushPromptDismissed();
	return subscription;
}

export async function unsubscribeFromNewPhotosPush() {
	clearPushSubscribedLocally();
	if (!("serviceWorker" in navigator)) {
		if (getAuthToken()) await postPushUnsubscribeAll();
		return;
	}
	const registration = await navigator.serviceWorker.ready;
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
}
