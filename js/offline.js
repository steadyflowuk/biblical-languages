// Saving Bible data for offline use (Session 12 deep check). The app itself is saved by the service worker (sw.js);
// Bible books and dictionary files are saved as they're opened. Two helpers fill the gaps:
// - warmEssentials(): after the app opens online, quietly saves the books the lessons, the Letters tab's read-aloud
//   verses and the dictionary's search lists need, so lessons and searching work offline from then on.
// - saveEverything(): Settings › "Save it all for offline use" fetches every file in data/files.json.
// Files go through the service worker, which keeps them in its data cache (data-v1).
import * as data from "./data.js";

const CACHE = "data-v1";
const has = async (cache, url) => !!(cache && await cache.match(new URL(url, location.href).href));
const openCache = async () => (window.caches ? caches.open(CACHE) : null);

/** Fetch the files not saved yet, a few at a time; onProgress(done, total). Returns how many are saved. */
async function fetchMissing(urls, onProgress, parallel) {
  const cache = await openCache();
  if (!cache || !navigator.serviceWorker || !navigator.serviceWorker.controller) return 0;
  const missing = [];
  for (const u of urls) if (!(await has(cache, u))) missing.push(u);
  let done = urls.length - missing.length;
  if (onProgress) onProgress(done, urls.length);
  let i = 0;
  const worker = async () => {
    while (i < missing.length) {
      const u = missing[i++];
      try {
        const res = await fetch(u);
        if (res.ok) await res.arrayBuffer(); // read it through so the service worker finishes saving it
        done++;
      } catch (e) { /* offline part-way: try again next time */ }
      if (onProgress) onProgress(done, urls.length);
    }
  };
  await Promise.all(Array.from({ length: parallel || 2 }, worker));
  return done;
}

/** The books lessons and the alphabet guide read from, and the dictionary's search lists. */
export async function essentialFiles() {
  const [index, books] = await Promise.all([data.getJSON("lessons/index.json"), data.books()]);
  const files = (index.grc || []).concat(index.he || []).filter((e) => e.file).map((e) => e.file)
    .concat(["lessons/alphabet/grc.json", "lessons/alphabet/he.json"]);
  const ids = new Set();
  for (const f of files) {
    const text = JSON.stringify(await data.getJSON(f).catch(() => ({})));
    (text.match(/"ref":"([0-9A-Z]{3}) \d+:\d+/g) || []).forEach((m) => ids.add(m.slice(7, 10)));
  }
  const out = ["data/lex/greek-index.json", "data/lex/hebrew-index.json"];
  ids.forEach((id) => {
    const b = books.find((x) => x.id === id);
    if (!b) return;
    out.push(`data/${b.lang === "grc" ? "gnt" : "hot"}/${id}.json`, `data/bsb/${id}.json`);
  });
  return out;
}

let warming = null;
/** Once per opening, when online and not saving data: save what lessons need (missing files only). */
export function warmEssentials() {
  if (warming) return warming;
  const c = navigator.connection;
  if (!navigator.onLine || (c && c.saveData)) return Promise.resolve(0);
  warming = essentialFiles().then((urls) => fetchMissing(urls, null, 2)).catch(() => 0);
  return warming;
}

/** Everything in data/files.json: { files: [[path, bytes]], bytes }. */
export const fileList = () => fetch("data/files.json", { cache: "no-store" }).then((r) => r.json());

/** How much of everything is saved: { saved, total, bytes, missingBytes }. */
export async function savedState() {
  const list = await fileList();
  const cache = await openCache();
  let saved = 0;
  let missingBytes = 0;
  for (const [p, size] of list.files) {
    if (await has(cache, p)) saved++;
    else missingBytes += size;
  }
  return { saved, total: list.files.length, bytes: list.bytes, missingBytes };
}

/** Save every data file; onProgress(done, total). */
export async function saveEverything(onProgress) {
  const list = await fileList();
  return fetchMissing(list.files.map((f) => f[0]), onProgress, 4);
}
