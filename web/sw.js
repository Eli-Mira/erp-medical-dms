/* App-shell service worker (P2.7 / client-prototype r2).
 *
 * Network-first for the stable shell files (index, styles, app.js, i18n) so the
 * user always runs the currently deployed bytes while online; the cache pair is
 * only the offline fallback. API requests are NEVER served from, nor written to,
 * the cache — the server is authoritative (a previous cache-first shell caused
 * stale screens after deploys). Bumping CACHE invalidates older copies.
 */
const CACHE = "medsys-shell-v9";
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
  const req = e.request;
  if (req.method !== "GET") return; // POST/PUT/DELETE: always network.
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // fonts CDN: let the browser handle it.
  const path = url.pathname;
  // Backend calls: network only. Never cached, no offline shim for data.
  if (path === "/meta" || path === "/health" ||
      /^\/(auth|master|invoices|inventory|ar|collections|payments)\b/.test(path)) {
    return;
  }
  const isShell = SHELL.indexOf(path) >= 0;
  const isNav = req.mode === "navigate";
  if (!isShell && !isNav) return;
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && isShell) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req)
          .then((hit) => hit || (isNav ? caches.match("/app/index.html") : undefined))
          .then((fallback) =>
            fallback ||
            new Response("offline", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } })
          )
      )
  );
});
