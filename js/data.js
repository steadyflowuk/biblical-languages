// Loads the app's Bible data (built by tools/build_data.py) and keeps it in memory.
// Files are cached for offline use by the service worker the first time they load.

const cache = new Map();
// Bible book files are large (Old Testament books up to 3.5 MB in memory), so only the most recently used
// few are kept here; the rest stay saved by the service worker and reload quickly from there.
// Dictionary entry files (data/lex/G|H/nn.json) are kept the same way, in a group of their own.
const GROUPS = [{ re: /^data\/(gnt|hot|bsb)\//, keep: 6 }, { re: /^data\/lex\/[GH]\//, keep: 8 }];
const groupOf = (path) => GROUPS.find((g) => g.re.test(path));

export function getJSON(path) {
  const group = groupOf(path);
  if (cache.has(path) && group) {
    const p = cache.get(path); // mark as recently used
    cache.delete(path);
    cache.set(path, p);
  }
  if (!cache.has(path)) {
    if (group) {
      const same = [...cache.keys()].filter((k) => group.re.test(k));
      same.slice(0, Math.max(0, same.length - group.keep + 1)).forEach((k) => cache.delete(k));
    }
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
