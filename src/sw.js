import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("push", (event) => {
	let payload = {
		title: "ANTRASHA",
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

	event.waitUntil(
		self.registration.showNotification(payload.title, {
			body: payload.body,
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
