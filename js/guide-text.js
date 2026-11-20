// The Guide's text (19 Nov 2026): turning an entry's written markup into HTML, reading a grammar label into the
// terms it is made of, and searching. No DOM here, so the checkers (tools/check_guide.mjs) run the same code in Node.
import { sayButton, heVoice } from "./audio.js";

export const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// a Greek or Hebrew word inside English text (a maqqef splits Hebrew words; an elision mark stays with its word)
const GREEK_WORD = /[Ͱ-Ͽἀ-῿][Ͱ-Ͽἀ-῿̀-ͯ’᾽]*/g;
const HEBREW_WORD = /[א-ת][֑-ֽֿ-ׇא-ת]*/g;
const GREEK_PUNCT = /[;·]+$/; // ; · at the end of a word are punctuation, not part of it

/** Letters named on their own (η, ει, σα, ח): no accent, breathing or vowel point. Shown, not said. */
export const isLetters = (lang, w) => (lang === "grc" ? w.length <= 1 || (w.length <= 3 && !/[\u0300-\u036f]/.test(w.normalize("NFD"))) : !/[\u05b0-\u05bb\u05c7]/.test(w)); // a Hebrew root (קדשׁ): letters, no vowels

/** A Greek word in the text: tap to hear it. Endings and stems written with a hyphen (-ομεν) are shown, not said. */
function greekWord(word, before, after) {
  const punct = (word.match(GREEK_PUNCT) || [""])[0];
  const w = punct ? word.slice(0, -punct.length) : word;
  if (!w) return esc(word);
  if (before === "-" || after === "-" || isLetters("grc", w)) return `<span lang="grc" class="g-grc">${esc(w)}</span>${esc(punct)}`;
  return `<button type="button" class="g-say" lang="grc" data-say="${esc(w)}" data-say-lang="grc" aria-label="Listen: ${esc(w)}">${esc(w)}</button>${esc(punct)}`;
}

/** A Hebrew word: said as the Reader says one real occurrence of it (guide/examples.json "words"). */
function hebrewWord(word, before, after, voices) {
  if (before === "-" || after === "-" || isLetters("he", word)) return `<bdi lang="he" dir="rtl" class="g-he">${esc(word)}</bdi>`;
  const v = voices && voices[word];
  const say = v ? heVoice(v[0], word, false, v[1]) : word;
  return `<bdi lang="he" dir="rtl"><button type="button" class="g-say" lang="he" data-say="${esc(say)}" data-say-lang="he" aria-label="Listen: ${esc(word)}">${esc(word)}</button></bdi>`;
}

/** The Greek and Hebrew words in a piece of English text (for the checkers). */
export function originalWords(text) {
  const out = [];
  const s = String(text || "");
  for (const m of s.matchAll(GREEK_WORD)) {
    const w = m[0].replace(GREEK_PUNCT, "");
    const before = s.charAt(m.index - 1);
    const after = s.charAt(m.index + m[0].length);
    if (w) out.push({ lang: "grc", word: w, part: before === "-" || after === "-" || isLetters("grc", w) });
  }
  for (const m of s.matchAll(HEBREW_WORD)) {
    const before = s.slice(0, m.index).replace(/[\u0591-\u05c7]+$/, "").slice(-1);
    const after = s.charAt(m.index + m[0].length);
    out.push({ lang: "he", word: m[0], part: before === "-" || after === "-" || isLetters("he", m[0]) });
  }
  return out;
}

// Words that keep their capital when a title is used as link text: names of languages, texts, people and stems
const PROPER = /^(Greek|Hebrew|Aramaic|Koine|Biblical|Septuagint|Masoretes|Erasmian|Restored|Strong's|Qal|Niphal|Piel|Pual|Hiphil|Hophal|Hithpael|Peal|Peil|Pael|Haphel|Hitpeel|Wayyiqtol|Weqatal|Weyiqtol|English|SBL|BSB|ESV|LXX)\b/;
/** The words a link to an entry shows when the text gives none: its title before any colon, as in running text. */
export function linkText(e) {
  let t = String(e.title || "").split(":")[0].replace(/\s*\(.*?\)\s*/g, " ").trim().replace(/^The /, "");
  if (!PROPER.test(t)) t = t.charAt(0).toLowerCase() + t.slice(1);
  return t;
}

/**
 * Markup → HTML. ctx: {entries: {id: entry}, books: {ID: name}, counts: {KEY: "1,234"}, voices}.
 *   [[id]] [[id|words]] → a link to that entry ([[#/route|words]] → a screen of the app);
 *   [JHN 3:16] [JHN 3:16|words] → the Reader; {{KEY}} → a number counted from the text; *words* → emphasis;
 *   Greek and Hebrew → tap to hear.
 */
export function renderText(text, ctx) {
  const c = ctx || {};
  const slots = [];
  const keep = (html) => `\u0000${slots.push(html) - 1}\u0000`;
  let s = String(text || "");
  s = s.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, id, words) => {
    if (id.startsWith("#/")) return keep(`<a href="${esc(id)}">${esc(words || id)}</a>`);
    const e = c.entries && c.entries[id];
    if (!e) return keep(esc(words || id)); // the checker fails on a link to no entry
    return keep(`<a class="g-link" href="#/guide/${esc(id)}">${renderInline(words || linkText(e), c)}</a>`);
  });
  s = s.replace(/\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)(?:\|([^\]]+))?\]/g, (m, bk, ch, v, words) => {
    const name = (c.books && c.books[bk]) || bk;
    return keep(`<a class="g-ref" href="#/read/${bk}/${ch}/${v}">${esc(words || `${name} ${ch}:${v}`)}</a>`);
  });
  s = s.replace(/\{\{([a-z0-9-]+)\}\}/g, (m, key) => keep(esc((c.counts && c.counts[key]) || "?")));
  return renderInline(s, c).replace(/\u0000(\d+)\u0000/g, (m, i) => slots[Number(i)]);
}

function renderInline(s, c) {
  let html = esc(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(GREEK_WORD, (w, i, all) => greekWord(w, all.charAt(i - 1), all.charAt(i + w.length)));
  // -ַיִם: an ending's hyphen comes before its first vowel sign
  html = html.replace(HEBREW_WORD, (w, i, all) => hebrewWord(w, all.slice(0, i).replace(/[\u0591-\u05c7]+$/, "").slice(-1), all.charAt(i + w.length), c.voices));
  return html;
}

/** Plain text of markup (for search and for the checkers' sentence counts). */
export function plainText(text, ctx) {
  const c = ctx || {};
  return String(text || "")
    .replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, id, words) => words || (c.entries && c.entries[id] ? linkText(c.entries[id]) : id))
    .replace(/\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)(?:\|([^\]]+))?\]/g, (m, bk, ch, v, words) => words || `${(c.books && c.books[bk]) || bk} ${ch}:${v}`)
    .replace(/\{\{([a-z0-9-]+)\}\}/g, (m, key) => (c.counts && c.counts[key]) || "")
    .replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1");
}

// ---------------------------------------------------------------- grammar labels → terms

/** The language of a grammar code: Greek, Hebrew or Aramaic (STEPBible's Hebrew codes start H, Aramaic A). */
export const codeLang = (lang, code) => (lang === "grc" ? "grc" : String(code || "").startsWith("A") ? "arc" : "he");

const tokens = (s) => String(s || "").toLowerCase().replace(/[(),:]/g, " ").split(/\s+/).filter(Boolean);
// words that join the terms of a label and need no entry of their own
export const LABEL_GLUE = new Set(["or", "of", "a", "and", "the", "with", "from"]);

/** Which entries may explain a label in this language: its own first, then Hebrew for Aramaic, then any language. */
function rank(entryLang, lang) {
  if (entryLang === lang) return 0;
  if (lang === "arc" && entryLang === "he") return 1;
  if (!entryLang || entryLang === "both") return 2;
  return -1;
}

/** The phrases every entry explains, longest first: [{words: [...], id, note, rank}]. */
export function phraseTable(guide) {
  const out = [];
  for (const e of guide.entries) {
    for (const m of e.match || []) {
      const [phrase, note] = m.split("=");
      out.push({ words: tokens(phrase), id: e.id, note: (note || "").trim(), lang: e.lang || "" });
    }
  }
  return out.sort((a, b) => b.words.length - a.words.length);
}

/**
 * A grammar label as shown in the app, read into its terms: [{text, id, note}] (id null for a word no entry explains;
 * glue words such as "or" are left out). lang: "grc" | "he" | "arc".
 */
export function labelTerms(label, lang, table) {
  const words = tokens(label);
  const out = [];
  let i = 0;
  while (i < words.length) {
    let best = null;
    for (const p of table) {
      const r = rank(p.lang, lang);
      if (r < 0 || p.words.length > words.length - i) continue;
      if (p.words.every((w, k) => words[i + k] === w)) {
        if (!best || p.words.length > best.words.length || (p.words.length === best.words.length && r < best.r)) best = { ...p, r };
      }
    }
    if (best) {
      out.push({ text: words.slice(i, i + best.words.length).join(" "), id: best.id, note: best.note });
      i += best.words.length;
    } else {
      if (!LABEL_GLUE.has(words[i])) out.push({ text: words[i], id: null, note: "" });
      i += 1;
    }
  }
  return out;
}

// ---------------------------------------------------------------- search

const fold = (s) => String(s || "").normalize("NFD").replace(/[̀-֑ͯ-ׇ]/g, "").toLowerCase().trim();

/** Entries for a search, best first: [{entry, score, why}]. */
export function searchGuide(query, guide, ctx) {
  const q = fold(query);
  const raw = String(query || "").trim();
  if (!q) {
    // a mark on its own (ְ, ־, ׃): fold() removes it, so look for it as written among the other names
    if (!raw) return [];
    return guide.entries.filter((e) => (e.aka || []).indexOf(raw) >= 0 || e.title.indexOf(raw) >= 0).map((e) => ({ entry: e, score: 90, why: raw }));
  }
  const words = q.split(/\s+/).filter(Boolean);
  const out = [];
  for (const e of guide.entries) {
    const title = fold(e.title);
    const aka = (e.aka || []).map(fold);
    const match = (e.match || []).map((m) => fold(m.split("=")[0]));
    let score = 0;
    let why = "";
    if (title === q) score = 100;
    else if (aka.includes(q)) { score = 90; why = (e.aka || [])[aka.indexOf(q)]; }
    else if (match.includes(q)) score = 85;
    else if (title.startsWith(q)) score = 70;
    else if (aka.some((a) => a.startsWith(q))) { score = 60; why = (e.aka || [])[aka.findIndex((a) => a.startsWith(q))]; }
    else {
      const short = fold(plainText(e.short, ctx));
      const body = fold((e.body || []).map((b) => plainText(b.p || b.h || (b.ul || []).join(" ") || (b.table ? [b.table.caption, ...b.table.head, ...b.table.rows.flat()].join(" ") : ""), ctx)).join(" "));
      const all = `${title} ${aka.join(" ")} ${short}`;
      if (words.every((w) => all.includes(w))) score = 40;
      else if (words.every((w) => all.includes(w) || body.includes(w))) score = 20;
    }
    if (score) out.push({ entry: e, score, why });
  }
  return out.sort((a, b) => b.score - a.score || a.entry.title.localeCompare(b.entry.title));
}

/** A query that looks like one of STEPBible's grammar codes: V-2AAI-3S, N-NSM, HVqp3ms, HC/Vqw3ms, AVpu2ms. */
export const looksLikeCode = (q) => /^[A-Z]{1,4}(-[0-9A-Z]{1,6})*$/.test(q) || /^[HA][A-Za-z0-9]+(\/[A-Za-z0-9]+)*$/.test(q);

/** The link under a word's grammar, everywhere in the app: each part of the label explained (#/guide/code/…). */
export const explainLink = (lang, code) => (code ? ` <a class="g-explain" href="#/guide/code/${lang === "he" ? "he" : "grc"}/${encodeURIComponent(code)}">What do these words mean?</a>` : "");

/** Listen button for a word of an example (sayButton without a level: the Guide works like the dictionary). */
export const listen = (text, lang, options) => sayButton(text, lang, options);
