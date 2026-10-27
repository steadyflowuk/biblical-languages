// Offline support. Bump VERSION whenever app files change so phones pick up the update.
const VERSION = "2026-10-27.14";
const SHELL = `shell-${VERSION}`;
const DATA = "data-v1"; // Bible books and lexicons: kept across app updates, refreshed in the background

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
  "js/data.js",
  "js/reader.js",
  "js/hebrew.js",
  "js/nav.js",
  "js/dictionary.js",
  "js/esv.js",
  "js/lessons.js",
  "lessons/index.json",
  "lessons/grc/0.json",
  "lessons/grc/1.json",
  "lessons/grc/2.json",
  "lessons/grc/3.json",
  "lessons/grc/4.json",
  "lessons/grc/5.json",
  "lessons/grc/6.json",
  "lessons/grc/7.json",
  "lessons/grc/8.json",
  "lessons/grc/9.json",
  "lessons/he/0.json",
  "data/morph/greek.json",
  "data/morph/hebrew.json",
  "data/books.json",
  "data/votd.json",
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

  // Bible data: use the saved copy at once, and refresh it in the background so corrections arrive
  if (url.pathname.includes("/data/")) {
    event.respondWith(
      caches.open(DATA).then(async (cache) => {
        const hit = await cache.match(req) || await caches.match(req);
        const refresh = fetch(req).then((res) => {
          if (res.ok) cache.put(req, res.clone());
          return res;
        }).catch(() => hit);
        return hit || refresh;
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
