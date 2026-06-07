import { apiUrl, ensureSessionId, getAuthToken } from "../api/client.js";

export const PUSH_PROMPT_DISMISSED_KEY = "antrasha_push_prompt_dismissed";
export const PUSH_SUBSCRIBED_KEY = "antrasha_push_subscribed";

export function isPushSupported() {
	return (
		typeof window !== "undefined" &&
		"serviceWorker" in navigator &&
		"PushManager" in window &&
		"Notification" in window
	);
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
	await ensureSessionId();
	const json = subscription.toJSON();
	const headers = {
		"Content-Type": "application/json",
		"X-Session-Id": localStorage.getItem("antrasha_session_id"),
	};
	const token = getAuthToken();
	if (token) headers.Authorization = `Bearer ${token}`;

	const res = await fetch(apiUrl("/push/subscribe"), {
		method: "POST",
		headers,
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
		throw new Error("Браузер не поддерживает push-уведомления");
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

	const registration = await navigator.serviceWorker.ready;
	const subscription = await registration.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: urlBase64ToUint8Array(publicKey),
	});

	await postPushSubscription(subscription, scope);
	markPushSubscribedLocally();
	markPushPromptDismissed();
	return subscription;
}
