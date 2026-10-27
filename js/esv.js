// The ESV, fetched from Crossway's API with the reader's own free key (api.esv.org).
// Crossway's terms (api.esv.org): no more than 500 verses or half a book, whichever is less, per request, on a page,
// or stored on the device (one- and two-chapter books are excepted for requests); do not change the words; identify
// the text as ESV; link to www.esv.org; show the copyright notice; never share the key; non-commercial use only.
// So: one chapter per request; the page holds only the chapters it shows; a small offline store that keeps under
// 450 verses in all and under half of any book (so a one-chapter book is never stored), refreshed after 30 days.
// The key and the store are kept under their own names, so backups (which copy "ao:" settings) never include them.

const KEY = "esv:key";
const STORE = "esv:chapters";
const MAX_STORED_VERSES = 450;
const MAX_AGE = 30 * 24 * 60 * 60 * 1000;

export const NOTICE = "Scripture quotations marked ESV are from the ESV® Bible (The Holy Bible, English Standard Version®), " +
  "© 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved. " +
  "The ESV text may not be quoted in any publication made available to the public by a Creative Commons license. " +
  "The ESV may not be translated into any other language. Users may not copy or download more than 500 verses of " +
  "the ESV Bible or more than one half of any book of the ESV Bible.";

const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); return true; } catch { return false; } };

export const getKey = () => (read(KEY) || "").trim();
export const hasKey = () => !!getKey();
/** Accepts the key alone or as copied from the ESV site ("Token abc…" or "Authorization: Token abc…"). */
export function setKey(raw) {
  const key = String(raw || "").replace(/^\s*(authorization:\s*)?token\s+/i, "").trim();
  write(KEY, key || null);
  memory.clear();
  return key;
}
export function clearKey() {
  write(KEY, null);
  write(STORE, null);
  memory.clear();
}

// ---------------------------------------------------------------- the offline store (≤ 450 verses)

function stored() {
  try { return JSON.parse(read(STORE) || "[]"); } catch { return []; }
}
const count = (l) => l.reduce((n, [, v]) => n + Object.keys(v).length, 0);
/** Keep a chapter for offline reading, within the limits: < half its book (bookVerses) and ≤ 450 verses in all. */
function remember(id, verses, bookVerses) {
  const now = Date.now();
  const half = Math.floor((bookVerses || 0) / 2);
  let list = stored().filter(([k, , t]) => k !== id && now - t < MAX_AGE);
  if (Object.keys(verses).length < half) {
    list.push([id, verses, now]);
    const book = id.slice(0, 2);
    const same = () => list.filter(([k]) => k.slice(0, 2) === book);
    while (count(same()) >= half) list.splice(list.indexOf(same()[0]), 1); // oldest chapter of this book first
    while (list.length > 1 && count(list) > MAX_STORED_VERSES) list.shift(); // then oldest overall
  }
  if (count(list) > MAX_STORED_VERSES) list = [];
  write(STORE, JSON.stringify(list));
}
function recall(id) {
  const hit = stored().find(([k, , t]) => k === id && Date.now() - t < MAX_AGE);
  return hit ? hit[1] : null;
}

// ---------------------------------------------------------------- fetching and reading a chapter

const memory = new Map(); // the chapters on the current page (at most 2): chapter id → Promise of { n: text }

/** Split the API's plain text into verses. Text before verse 1 is a psalm's title (verse 0). */
export function parseChapter(passage, isPsalm) {
  const verses = {};
  // Song of Songs speaker labels ("She", "He", "Others") stand alone like headings: leave them out
  const lines = String(passage || "").split("\n").map((l) => l.trim());
  const kept = lines.filter((l, i) => !(l && !/[.,;:!?’”)]$/.test(l) && !/\[\d+\]/.test(l) && l.split(/\s+/).length <= 3
    && !lines[i - 1] && !lines[i + 1] && !/^Selah$/i.test(l)));
  const text = kept.join("\n");
  const parts = text.split(/\[(\d+)\]/);
  // Text that introduces the next verse belongs with it, not at the end of this one: the ESV's double brackets
  // ("[[" before Mark 16:9 and John 7:53) and its bracketed notes ("[Some of the earliest manuscripts …]").
  for (let i = 0; i < parts.length - 2; i += 2) {
    const m = parts[i].match(/(\n\s*\[[^\]\d[][^\]]*\])?\s*(\[\[)?\s*$/);
    if (m && m[0].trim()) {
      parts[i] = parts[i].slice(0, m.index);
      parts[i + 2] = `${m[0].trim()} ${parts[i + 2]}`;
    }
  }
  const before = parts[0].replace(/\s+/g, " ").trim();
  if (before && isPsalm) verses[0] = before;
  for (let i = 1; i < parts.length; i += 2) {
    const n = Number(parts[i]);
    const t = parts[i + 1].replace(/\s+/g, " ").replace(/\[\[ /g, "[[").trim();
    if (t) verses[n] = verses[n] ? `${verses[n]} ${t}` : t;
  }
  return verses;
}

export class EsvError extends Error {
  constructor(kind, message) { super(message); this.kind = kind; }
}

/** One chapter of the ESV as { verse number: text }. bookNumber is 1 (Genesis) to 66 (Revelation);
 * bookVerses is the number of verses in the book (for the half-a-book storage limit). */
export function chapter(bookNumber, ch, bookVerses) {
  const id = String(bookNumber).padStart(2, "0") + String(ch).padStart(3, "0");
  if (memory.has(id)) {
    const p = memory.get(id);
    memory.delete(id);
    memory.set(id, p); // most recent last
    return p;
  }
  const p = (async () => {
    const key = getKey();
    if (!key) throw new EsvError("nokey", "Add your ESV key in Settings to read the ESV.");
    const kept = recall(id);
    if (kept) return kept;
    const q = `${id}001-${id}999`;
    const params = "include-headings=false&include-footnotes=false&include-short-copyright=false&include-copyright=false" +
      "&include-passage-references=false&include-verse-numbers=true&include-first-verse-numbers=true" +
      "&include-passage-horizontal-lines=false&include-heading-horizontal-lines=false&indent-poetry=false" +
      "&indent-paragraphs=0&include-selahs=true";
    let res;
    try {
      res = await fetch(`https://api.esv.org/v3/passage/text/?q=${q}&${params}`, { headers: { Authorization: `Token ${key}` } });
    } catch {
      throw new EsvError("offline", "The ESV needs an internet connection for chapters you haven't read recently.");
    }
    if (res.status === 401 || res.status === 403) throw new EsvError("auth", "The ESV key wasn't accepted. Check it in Settings.");
    if (res.status === 429) throw new EsvError("limit", "The ESV has had too many requests for now. Try again in a little while.");
    if (!res.ok) {
      throw new EsvError("other", "The ESV couldn't load just now.");
    }
    const json = await res.json();
    const verses = parseChapter((json.passages || [])[0], bookNumber === 19);
    remember(id, verses, bookVerses);
    return verses;
  })();
  memory.set(id, p);
  p.catch(() => memory.delete(id)); // try again next time
  while (memory.size > 2) memory.delete(memory.keys().next().value);
  return p;
}

/** Check a key by fetching one verse (Settings). */
export async function testKey(key) {
  try {
    const res = await fetch("https://api.esv.org/v3/passage/text/?q=John+3:16&include-headings=false&include-footnotes=false" +
      "&include-short-copyright=false&include-passage-references=false&include-verse-numbers=false",
    { headers: { Authorization: `Token ${key}` } });
    if (res.status === 401 || res.status === 403) return { ok: false, message: "That key wasn't accepted. Check you copied all of it." };
    if (!res.ok) return { ok: false, message: "The ESV couldn't be reached just now. Try again in a moment." };
    const json = await res.json();
    return { ok: true, sample: String((json.passages || [])[0] || "").replace(/\s+/g, " ").trim() };
  } catch {
    return { ok: false, message: "No connection. Connect to the internet to check the key." };
  }
}
