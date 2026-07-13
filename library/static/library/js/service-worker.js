const CACHE_VERSION = "pap-v3";
const PRECACHE = [
  "/static/library/css/app.css",
  "/static/library/js/app.js",
  "/static/library/js/pwa.js",
  "/static/library/offline.html",
  "/static/library/icons/icon-192.png",
  "/static/library/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then((cache) => Promise.allSettled(PRECACHE.map((url) => cache.add(url))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/static/library/");
}

function isApiOrAdmin(url) {
  return url.pathname.startsWith("/api/") || url.pathname.startsWith("/admin/");
}

function isShareTargetRequest(url, method) {
  return (method === "POST" || method === "GET") && url.pathname === "/share/";
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isApiOrAdmin(url)) return;

  if (isShareTargetRequest(url, request.method)) {
    event.respondWith(
      (async () => {
        const response = await fetch(request, { redirect: "follow", credentials: "include" });
        if (response.redirected) {
          return Response.redirect(response.url, 303);
        }
        return response;
      })(),
    );
    return;
  }

  if (request.method !== "GET") return;

  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          }
          return response;
        });
        return cached || network;
      }),
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => response)
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match("/static/library/offline.html")),
        ),
    );
  }
});
