import { setCacheNameDetails } from "workbox-core";
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";

setCacheNameDetails({
  prefix: "antrasha-work",
  suffix: "v1",
  precache: "precache",
  runtime: "runtime",
});

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
