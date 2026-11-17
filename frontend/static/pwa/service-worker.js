const CACHE_NAME = "carestance-site-v2";
const OFFLINE_PAGE = "/static/pwa/offline.html";
const CACHED_ASSETS = [
  OFFLINE_PAGE,
  "/static/pwa/icon-192.png",
  "/static/pwa/icon-512.png",
  "/static/css/pwa.css",
  "/static/js/pwa.js",
];
const CACHED_ASSET_PATHS = new Set(CACHED_ASSETS);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(CACHED_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((cacheName) => cacheName.startsWith("carestance-site-") && cacheName !== CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const requestUrl = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    requestUrl.origin !== self.location.origin
  ) {
    return;
  }

  if (CACHED_ASSET_PATHS.has(requestUrl.pathname)) {
    event.respondWith(
      caches.match(event.request, { ignoreSearch: true })
        .then((cachedResponse) => cachedResponse || fetch(event.request))
    );
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(async () => {
        return (await caches.match(OFFLINE_PAGE)) || Response.error();
      })
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : "" };
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || "CareStance", {
      body: payload.body || "You have a new update.",
      icon: "/static/pwa/icon-192.png",
      badge: "/static/pwa/icon-192.png",
      data: { url: payload.url || "/" },
      tag: "carestance-update",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin);
  const targetUrl = target.origin === self.location.origin ? target.href : self.location.origin;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const existingClient = clients.find((client) => new URL(client.url).origin === self.location.origin);
      if (existingClient) {
        return existingClient.navigate(targetUrl).then(() => existingClient.focus());
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
