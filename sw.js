// Offline support. Bump VERSION whenever app files change so phones pick up the update.
const VERSION = "2026-10-26.2";
const SHELL = `shell-${VERSION}`;
const DATA = "data-v1"; // Bible data, kept across app updates (added in Session 2)

const SHELL_FILES = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "css/app.css",
  "js/app.js",
  "js/store.js",
  "js/screens.js",
  "js/install.js",
  "js/verses.js",
  "assets/fonts/atkinson-regular.woff",
  "assets/fonts/atkinson-bold.woff",
  "assets/fonts/gentium-plus-regular.woff",
  "assets/fonts/gentium-plus-bold.woff",
  "assets/fonts/gentium-plus-italic.woff",
  "assets/fonts/noto-serif-hebrew.woff",
  "assets/icons/icon-192.png",
  "assets/icons/icon-512.png",
  "assets/icons/apple-touch-icon.png",
  "assets/icons/favicon-64.png",
];

self.addEventListener("install", (event) => {
  // cache: "reload" skips the browser's HTTP cache so a new version never stores stale files
  event.waitUntil(
    caches.open(SHELL)
      .then((c) => c.addAll(SHELL_FILES.map((f) => new Request(f, { cache: "reload" }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("shell-") && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // videos, ESV etc. go straight to the network

  // Page loads: always serve the app shell
  if (req.mode === "navigate") {
    event.respondWith(caches.match("index.html").then((r) => r || fetch(req)));
    return;
  }

  // Bible data: keep once downloaded
  if (url.pathname.includes("/data/")) {
    event.respondWith(
      caches.open(DATA).then(async (cache) => {
        const hit = await cache.match(req);
        if (hit) return hit;
        const res = await fetch(req);
        if (res.ok) cache.put(req, res.clone());
        return res;
      })
    );
    return;
  }

  // App files: cached copy first, refresh in the background
  event.respondWith(
    caches.open(SHELL).then(async (cache) => {
      const hit = await cache.match(req, { ignoreSearch: true });
      const refresh = fetch(req).then((res) => {
        if (res.ok) cache.put(req, res.clone());
        return res;
      }).catch(() => hit);
      return hit || refresh;
    })
  );
});
