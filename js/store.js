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
  abcLang: "",             // grc | he: the last alphabet guide opened (Letters tab); "" = follow learnLang
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
  // Today and Progress (js/activity.js, js/progress.js)
  activity: {},            // "2026-10-28" → { r: cards reviewed, l: lesson steps, v: chapters read }
  bestStreak: 0,           // the longest run of study days
  lastBackup: "",          // when a backup was last saved (ISO date and time)
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

/** What a backup holds, for the "Restore this backup?" question. Throws if it isn't one of ours. */
export function backupSummary(backup) {
  if (!backup || backup.app !== "aleph-to-omega" || typeof backup.data !== "object" || !backup.data) {
    throw new Error("This file isn't an Aleph to Omega backup.");
  }
  const parse = (k, d) => { try { return JSON.parse(backup.data[PREFIX + k]) || d; } catch (e) { return d; } };
  const lessons = Object.values(parse("lessons", {})).filter((p) => p && p.done).length;
  const cards = Object.keys(parse("cards", {})).length;
  const at = backup.exported ? new Date(backup.exported) : null;
  const when = at && !isNaN(at) ? `on ${at.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })} at ${at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : "at an unknown time";
  return { lessons, cards, when };
}

/** Make this device's progress and settings the backup's: everything of ours is replaced (the ESV key stays). */
export function importBackup(backup) {
  backupSummary(backup); // throws if it isn't a backup
  try {
    const ours = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(PREFIX)) ours.push(k);
    }
    ours.forEach((k) => localStorage.removeItem(k));
  } catch (e) { /* storage unavailable: the writes below will say so */ }
  let count = 0;
  for (const [k, v] of Object.entries(backup.data)) {
    if (!k.startsWith(PREFIX) || typeof v !== "string") continue;
    localStorage.setItem(k, v);
    count++;
  }
  return count;
}
