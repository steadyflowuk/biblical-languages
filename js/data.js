// Loads the app's Bible data (built by tools/build_data.py) and keeps it in memory.
// Files are cached for offline use by the service worker the first time they load.

const cache = new Map();

export function getJSON(path) {
  if (!cache.has(path)) {
    const p = fetch(path).then((r) => {
      if (!r.ok) throw new Error(`Couldn't load ${path} (${r.status})`);
      return r.json();
    });
    p.catch(() => cache.delete(path)); // allow a retry after a failure
    cache.set(path, p);
  }
  return cache.get(path);
}

export const books = () => getJSON("data/books.json");
export const verseOfTheDay = () => getJSON("data/votd.json");
export const morph = (lang) => getJSON(`data/morph/${lang === "he" ? "hebrew" : "greek"}.json`);
export const bsb = (bookId) => getJSON(`data/bsb/${bookId}.json`);

/** Original-language text of a book: Greek NT (NA28) or Hebrew/Aramaic OT (Leningrad). */
export async function original(bookId) {
  const list = await books();
  const book = list.find((b) => b.id === bookId);
  if (!book) throw new Error(`No book ${bookId}`);
  return getJSON(`data/${book.lang === "grc" ? "gnt" : "hot"}/${bookId}.json`);
}

/** Words of one verse, or [] if the verse isn't in the original text (e.g. Matthew 17:21). */
export async function verseWords(bookId, chapter, verse) {
  const data = await original(bookId);
  const ch = data.ch.find(([c]) => c === chapter);
  const v = ch && ch[1].find(([n]) => n === verse);
  return v ? v[1] : [];
}

/** Pick the day's verse for each language. Same verse for everyone on a given day. */
export function pickForDay(verses, date = new Date()) {
  const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 864e5);
  const greek = verses.filter((v) => v.lang === "grc");
  const hebrew = verses.filter((v) => v.lang === "he");
  return { grc: greek[day % greek.length], he: hebrew[day % hebrew.length] };
}
