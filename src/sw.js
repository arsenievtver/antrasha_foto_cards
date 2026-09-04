import { setCacheNameDetails } from "workbox-core";
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";

setCacheNameDetails({
	prefix: "antrasha-client",
	suffix: "v1",
	precache: "precache",
	runtime: "runtime",
});

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

/** iOS добавляет «from ANTRASHA» — не дублируем бренд в title. */
const BRAND_TITLE = /^antrasha$/i;

function normalizePushDisplay({ title = "", body = "" } = {}) {
	const trimmedTitle = String(title).trim();
	const trimmedBody = String(body).trim();

	if (trimmedTitle && !BRAND_TITLE.test(trimmedTitle)) {
		return { title: trimmedTitle, body: trimmedBody };
	}

	if (!trimmedBody) {
		return { title: "Новинки", body: "" };
	}

	const newline = trimmedBody.indexOf("\n");
	if (newline >= 0) {
		return {
			title: trimmedBody.slice(0, newline).trim(),
			body: trimmedBody.slice(newline + 1).trim(),
		};
	}

	const sentenceEnd = trimmedBody.search(/[.!?](?:\s+|$)/);
	if (sentenceEnd >= 0 && sentenceEnd < 120) {
		return {
			title: trimmedBody.slice(0, sentenceEnd + 1).trim(),
			body: trimmedBody.slice(sentenceEnd + 1).trim(),
		};
	}

	return { title: trimmedBody, body: "" };
}

self.addEventListener("push", (event) => {
	let payload = {
		title: "",
		body: "Новые образы — оцените новинки",
		url: "/",
		tag: "antrasha-new-photos",
	};
	try {
		if (event.data) {
			payload = { ...payload, ...event.data.json() };
		}
	} catch {
		/* ignore malformed payload */
	}

	const display = normalizePushDisplay(payload);

	event.waitUntil(
		self.registration.showNotification(display.title, {
			body: display.body,
			icon: "/web-app-manifest-192x192.png",
			badge: "/web-app-manifest-192x192.png",
			tag: payload.tag || "antrasha-new-photos",
			data: { url: payload.url || "/" },
		}),
	);
});

self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	const rawUrl = event.notification.data?.url || "/";
	const targetUrl = new URL(rawUrl, self.location.origin).href;

	event.waitUntil(
		self.clients
			.matchAll({ type: "window", includeUncontrolled: true })
			.then((clientList) => {
				for (const client of clientList) {
					if (client.url.startsWith(self.location.origin) && "focus" in client) {
						return client.focus();
					}
				}
				if (self.clients.openWindow) {
					return self.clients.openWindow(targetUrl);
				}
				return undefined;
			}),
	);
});
