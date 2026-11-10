import { clientsClaim, setCacheNameDetails } from "workbox-core";
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";

setCacheNameDetails({
  prefix: "antrasha-work",
  suffix: "v1",
  precache: "precache",
  runtime: "runtime",
});

// Установленное на iPhone приложение почти не закрывается полностью — без этого
// новая версия ждала бы «закрытия всех вкладок» неделями.
self.skipWaiting();
clientsClaim();

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
