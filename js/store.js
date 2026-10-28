// Settings and progress kept on this device only.
// Every key starts with "ao:" so a backup can collect them all.

const PREFIX = "ao:";

const DEFAULTS = {
  textSize: "normal",      // normal | large | larger | largest
  theme: "auto",           // auto | light | dark
  greekVoice: "erasmian",  // erasmian | koine
  installTipDismissed: false,
  // Reader
  lastRead: "JHN/1",       // book/chapter to reopen
  lastLxx: "PSA/22",       // Septuagint book/chapter to reopen
  readLayout: "words",     // words (interlinear) | text (running text)
  showEnglish: true,       // English under each word
  showTranslit: false,     // pronunciation under each word
  showGrammar: false,      // short grammar under each word
  showBSB: true,           // Berean Standard Bible under each verse
  showESV: false,          // ESV under each verse (needs the reader's own key, see js/esv.js)
  showLXX: false,          // Septuagint under each Old Testament verse
  // Lessons (js/lessons.js)
  learnLang: "grc",        // grc | he: the path shown on Learn and Today
  lessons: {},             // id → { pos, retries, first, done, best, completed }
  reviewQueue: [],         // words from finished lessons: { k, lang, t, say, en, lesson, added }
  // Review (js/review.js): FSRS flashcards
  cards: {},               // "grc:G3056" → { id, lang, k, t, say, en, src, lesson, n, added, f: FSRS card }
  reviewLog: {},           // "2026-10-28" → { r: answers, n: new words } (the day starts at 4am)
  reviewDecks: { grc: false, he: false }, // the frequency word lists switched on
  newPerDay: 10,
  reviewLang: "all",       // all | grc | he
  reviewAutoPlay: false,   // say each card's word as it appears
  speechRate: "slow",      // slow | normal (js/audio.js)
  // Dictionary
  dictLang: "both",        // both | G | H
  recentWords: [],         // lexicon keys, most recent first
};

// A fresh copy each time: a caller that changes a default object ({} or []) must not change the default itself.
const fallback = (key) => (DEFAULTS[key] && typeof DEFAULTS[key] === "object" ? JSON.parse(JSON.stringify(DEFAULTS[key])) : DEFAULTS[key]);

export function get(key) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw === null ? fallback(key) : JSON.parse(raw);
  } catch {
    return fallback(key);
  }
}

export function set(key, value) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function applyDisplaySettings() {
  const root = document.documentElement;
  const size = get("textSize");
  if (size === "normal") root.removeAttribute("data-size");
  else root.setAttribute("data-size", size);

  const theme = get("theme");
  if (theme === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);

  const dark = theme === "dark" || (theme === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0C1322" : "#1E2B45");
}

// ---- Backup and restore ----

export function exportBackup() {
  const data = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(PREFIX)) data[k] = localStorage.getItem(k);
    }
  } catch { /* storage unavailable: export what we have */ }
  return {
    app: "aleph-to-omega",
    version: 1,
    exported: new Date().toISOString(),
    data,
  };
}

export function importBackup(backup) {
  if (!backup || backup.app !== "aleph-to-omega" || typeof backup.data !== "object") {
    throw new Error("This file isn't an Aleph to Omega backup.");
  }
  let count = 0;
  for (const [k, v] of Object.entries(backup.data)) {
    if (!k.startsWith(PREFIX) || typeof v !== "string") continue;
    localStorage.setItem(k, v);
    count++;
  }
  return count;
}
