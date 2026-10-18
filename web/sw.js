// Minimal app-shell service worker (P2.7). Cache-first; bump CACHE to invalidate.
const CACHE = "medsys-shell-v4";
const SHELL = [
  "/app/", "/app/index.html", "/app/manifest.webmanifest",
  "/app/icon.svg", "/app/styles.css", "/app/app.js",
  "/app/i18n/ar.json", "/app/i18n/en.json",
];

self.addEventListener("install", (e) =>
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
);

self.addEventListener("activate", (e) =>
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
);

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request)
          .then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
            return res;
          })
          .catch(() => caches.match("/app/index.html"))
    )
  );
});
