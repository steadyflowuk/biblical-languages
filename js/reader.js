// The Reader: a chapter of the Hebrew/Aramaic Old Testament or the Greek New Testament, word by word,
// with the BSB under each verse. Hebrew runs right to left; its helpers live in hebrew.js.
import * as store from "./store.js";
import * as data from "./data.js";
import {
  heText, heTranslit, heEnglish, heAfter, heJoined, heParagraphAfter, isAramaic, heParts, heMainKey,
  heShortGrammar, heFriendlyGrammar,
} from "./hebrew.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const MARKS = /[¶¬]/g; // paragraph mark and one stray symbol in the source: never shown

const GROUPS = {
  OT: [
    ["The Law", ["GEN", "EXO", "LEV", "NUM", "DEU"]],
    ["History", ["JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST"]],
    ["Poetry and wisdom", ["JOB", "PSA", "PRO", "ECC", "SNG"]],
    ["Major prophets", ["ISA", "JER", "LAM", "EZK", "DAN"]],
    ["Minor prophets", ["HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"]],
  ],
  NT: [
    ["Gospels and Acts", ["MAT", "MRK", "LUK", "JHN", "ACT"]],
    ["Paul's letters", ["ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM"]],
    ["Other letters and Revelation", ["HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"]],
  ],
};

/** "Psalm 23" rather than "Psalms 23". */
const chapterName = (book, ch) => `${book.id === "PSA" ? "Psalm" : book.name} ${ch}`;

// ---------------------------------------------------------------- small helpers

/** English for one word: drop verse-number notes and trailing punctuation; mark supplied and untranslated words. */
export function englishHTML(raw) {
  let s = String(raw || "")
    .replace(/^\s*(\{[^}]*\}|\[\d+(?:\.\d+)?\]|\(\d+[a-z]?\))\s*/, "") // verse notes like {8.1} [14] (26) (8b)
    .replace(/[,.;:·!?·;]+$/, "")
    .replace(/(\S)\[/g, "$1 [")
    .replace(/\s+/g, " ")
    .trim();
  s = esc(s)
    .replace(/&lt;(.*?)&gt;/g, '<span class="e-u" title="not needed in English">$1</span>')
    .replace(/\[(.*?)\]/g, '<span class="e-s" title="added for English">$1</span>')
    .replace(/&lt;|&gt;|[[\]]/g, ""); // a few source glosses have an unmatched bracket (e.g. Isa 7:23)
  return s;
}

const ABBR = [
  [/Definite article/i, "article"], [/Personal pronoun/i, "pronoun"], [/Relative pronoun/i, "rel. pronoun"],
  [/Demonstrative pronoun/i, "dem. pronoun"], [/Interrogative pronoun/i, "interr. pronoun"],
  [/\bnominative\b/gi, "nom."], [/\bgenitive\b/gi, "gen."], [/\bdative\b/gi, "dat."], [/\baccusative\b/gi, "acc."],
  [/\bvocative\b/gi, "voc."], [/\bsingular\b/gi, "sg."], [/\bplural\b/gi, "pl."], [/\bmasculine\b/gi, "masc."],
  [/\bfeminine\b/gi, "fem."], [/\bneuter\b/gi, "neut."], [/\bpresent\b/gi, "pres."], [/\bimperfect\b/gi, "impf."],
  [/\b2nd aorist\b/gi, "aor."], [/\baorist\b/gi, "aor."], [/\bfuture\b/gi, "fut."], [/\bpluperfect\b/gi, "plupf."],
  [/\bperfect\b/gi, "perf."], [/\bactive\b/gi, "act."], [/\bmiddle deponent\b/gi, "mid."], [/\bpassive deponent\b/gi, "pass."],
  [/\bmiddle or passive deponent\b/gi, "mid./pass."], [/\bmiddle or passive\b/gi, "mid./pass."], [/\bmiddle\b/gi, "mid."],
  [/\bpassive\b/gi, "pass."], [/\bindicative\b/gi, "ind."], [/\bsubjunctive\b/gi, "subj."], [/\bimperative\b/gi, "impv."],
  [/\binfinitive\b/gi, "inf."], [/\bparticiple\b/gi, "ptc."], [/\boptative\b/gi, "opt."], [/\badjective\b/gi, "adj."],
  [/\bpreposition\b/gi, "prep."], [/\bconjunction\b/gi, "conj."], [/\badverb\b/gi, "adv."], [/\bparticle\b/gi, "part."],
];

// The source tags proper nouns: individual = a person's name, location = a place name, title,
// and "… gentilic" = a word for a people group (e.g. Galilean). Replaced in one pass so labels never nest;
// "1st person" in pronouns is grammar and is left alone.
const TAG_RE = /\s+(?:(?:individual|person|location)\s+)?gentilic\b|\s+individual\b|\s+location\b|\s+title\b/gi;
const tagLabel = (m) => (/gentilic/i.test(m) ? " (people group)" : /individual/i.test(m) ? " (name of a person)"
  : /location/i.test(m) ? " (name of a place)" : " (title)");

/** Tidy a grammar description for learners: drop repeated words, explain the source's name tags. */
export function friendlyGrammar(desc) {
  const seen = new Set();
  let s = String(desc || "").split(" ").filter((w) => {
    const k = w.toLowerCase();
    if (seen.has(k) && !/^(or|of|a|singular|plural)$/.test(k)) return false;
    seen.add(k);
    return true;
  }).join(" ");
  return s.replace(TAG_RE, tagLabel);
}

/** "Verb aorist active indicative 3rd singular" → "verb aor. act. ind. 3rd sg." */
export function shortGrammar(desc) {
  let s = friendlyGrammar(desc);
  for (const [re, rep] of ABBR) s = s.replace(re, rep);
  return s.charAt(0).toLowerCase() + s.slice(1);
}

const compact = (gloss) => String(gloss || "").split(": ").pop();

/** STEPBible's extended numbers (G0025, G2424G) as the familiar Strong's numbers (G25, G2424). */
export const strongs = (key) => String(key || "").replace(/^([GH])0*(\d+)[A-Za-z]?$/, "$1$2");

// ---------------------------------------------------------------- BSB chapter → verses, headings, notes

function bsbChapter(bsbBook, ch) {
  const chapter = bsbBook?.chapters?.[ch - 1];
  const verses = new Map(); // verse → text with \u0001n\u0001 note markers
  const headings = new Map(); // verse → [heading]
  if (!chapter) return { verses, headings, notes: [] };
  let v = 0;
  let pending = [];
  for (const [kind, items] of chapter[0]) {
    if (kind === "s") { pending.push(items.filter((x) => typeof x === "string").join(" ")); continue; }
    if (kind === "r" || kind === "b") continue; // cross-reference lines and blank lines
    for (const x of items) {
      if (typeof x === "number") {
        v = x;
        if (pending.length) { headings.set(v, pending); pending = []; }
        if (!verses.has(v)) verses.set(v, "");
      } else if (typeof x === "string") {
        if (pending.length && v === 0) { headings.set(0, pending); pending = []; }
        verses.set(v, ((verses.get(v) || "") + " " + x).replace(/\s+/g, " ").trim());
      }
    }
  }
  return { verses, headings, notes: chapter[1] || [] };
}

function bsbHTML(text, notes, ch) {
  return esc(text).replace(/\u0001(\d+)\u0001/g, (m, i) =>
    notes[+i] ? `<button type="button" class="fn" data-note="${ch}:${+i}" aria-label="Translator's note">†</button>` : "");
}

const refLabel = (r) => r.replace(".", ":");

/** The English (BSB) verses an NA28 verse covers: usually its own number; see build_data.py for the exceptions. */
function englishRefs(state, verse) {
  return Array.isArray(verse[2]) ? verse[2] : [`${state.ch}.${verse[0]}`];
}

function bsbVerse(state, ref) {
  const [c, n] = ref.split(".").map(Number);
  if (c !== state.ch && !state.other[c]) state.other[c] = bsbChapter(state.bsbBook, c);
  const chap = c === state.ch ? state.bsb : state.other[c];
  const text = chap.verses.get(n);
  return text ? { text, notes: chap.notes, c, n } : null;
}

// ---------------------------------------------------------------- the sheet (word details, display, picker)

function openSheet(html, { label, onClose, returnFocus } = {}) {
  closeSheet();
  const wrap = document.createElement("div");
  wrap.className = "sheet";
  wrap.innerHTML = `<div class="sheet-backdrop" data-close></div>
    <section class="sheet-panel" role="dialog" aria-modal="true" aria-label="${esc(label || "Details")}" tabindex="-1">
      <button type="button" class="sheet-close" data-close aria-label="Close">×</button>
      <div class="sheet-body">${html}</div>
    </section>`;
  document.body.append(wrap);
  document.body.classList.add("sheet-open");
  // Make the page behind inactive so Tab and screen readers stay inside the open sheet
  for (const el of document.body.children) {
    if (el !== wrap && !el.hasAttribute("inert")) el.setAttribute("inert", ""), el.dataset.sheetInert = "1";
  }
  const panel = wrap.querySelector(".sheet-panel");
  const close = () => { closeSheet(); onClose?.(); returnFocus?.focus?.({ preventScroll: true }); };
  wrap.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", close));
  wrap.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  sheetEscape = (e) => { if (e.key === "Escape" && document.querySelector(".sheet")) close(); };
  document.addEventListener("keydown", sheetEscape);
  panel.focus({ preventScroll: true });
  return wrap.querySelector(".sheet-body");
}

let sheetEscape = null;

export function closeSheet() {
  document.querySelector(".sheet")?.remove();
  document.body.classList.remove("sheet-open");
  document.querySelectorAll("[data-sheet-inert]").forEach((el) => { el.removeAttribute("inert"); delete el.dataset.sheetInert; });
  if (sheetEscape) document.removeEventListener("keydown", sheetEscape);
  sheetEscape = null;
}

// ---------------------------------------------------------------- word details

const counts = {}; // language → Promise of Map(lexicon key → number of times in that Testament)
function wordCounts(he) {
  const file = he ? "hebrew" : "greek";
  if (!counts[file]) counts[file] = data.getJSON(`data/lex/${file}-index.json`).then((idx) => new Map(idx.map((e) => [e[0], e[4] || 0])));
  return counts[file];
}

/** Real Strong's numbers only: STEPBible's H9001+ are its own labels for prefixes, suffixes and punctuation. */
const realStrongs = (key) => (/^H(\d{4})/.test(key) && Number(key.slice(1, 5)) >= 9000 ? "" : strongs(key));
const plainGloss = (g) => compact(g).replace(/[[\]]/g, "");

const FLAG_NOTES = {
  q: "The scribes wrote this word one way but marked it to be read aloud another way. The text here shows how it is read aloud.",
  k: "Written in the Hebrew text but, by long tradition, not read aloud.",
  x: "Missing from the Leningrad Codex. It is supplied from other Hebrew manuscripts or early translations such as the Septuagint.",
};

function heWordSheetHTML(w, ctx) {
  const [, translit, english, , , , flag = "", note = ""] = w;
  const parts = heParts(w);
  const mainKey = heMainKey(w);
  const main = parts.find((p) => p.main) || parts[0] || { code: w[4] };
  const lex = ctx.lex[mainKey] || [heText(w), translit, ""];
  const strong = realStrongs(mainKey);
  const g = ctx.morph[main.code] || [main.code];
  const explain = g[1] ? `<span class="ws-explain">${esc(g[1].charAt(0).toUpperCase() + g[1].slice(1))}${g[2] ? `, as in “${esc(g[2])}”` : ""}.</span>` : "";
  const row = (dt, dd, cls = "") => `<div${cls ? ` class="${cls}"` : ""}><dt>${dt}</dt><dd>${dd}</dd></div>`;
  return `
    <p class="ws-ref">${esc(ctx.ref)}</p>
    <h2 class="ws-word he" lang="he" dir="rtl" id="sheet-title">${esc(heText(w))}</h2>
    <p class="ws-translit">${esc(heTranslit(translit))}</p>
    ${flag ? `<p class="ws-flag">${esc(FLAG_NOTES[flag] || "")}</p>` : ""}
    <dl class="ws-facts">
      ${flag === "q" && note ? row("Written", `<span lang="he" dir="rtl" class="ws-lemma">${esc(note)}</span>`) : ""}
      ${isAramaic(w) ? row("Language", "Aramaic") : ""}
      ${parts.length > 1 ? row("Word parts", `<ul class="ws-parts">${parts.map((p) => {
        const l = ctx.lex[p.key];
        const label = heShortGrammar((ctx.morph[p.code] || [p.code])[0]);
        return `<li${p.main ? ' class="main"' : ""}><span lang="he" dir="rtl" class="ws-lemma">${esc(p.text)}</span> ${esc(l ? plainGloss(l[2]) : "")} <span class="muted">(${esc(label)})</span></li>`;
      }).join("")}</ul>`) : ""}
      ${row("Dictionary form", `<span lang="he" dir="rtl" class="ws-lemma">${esc(lex[0])}</span> <span class="muted">${esc(heTranslit(lex[1]))}${strong ? ` · Strong's ${esc(strong)}` : ""}</span>`)}
      ${row("Meaning", esc(plainGloss(lex[2]) || "—"))}
      ${row("In this verse", englishHTML(heEnglish(english)) || "—")}
      ${row("Grammar", `<strong>${esc(heFriendlyGrammar(g[0]))}</strong>${explain}`)}
      <div class="ws-count" hidden><dt>How common</dt><dd></dd></div>
    </dl>
    ${ctx.bsb ? `<p class="ws-bsb"><span class="muted">${esc(ctx.bsbRef)} (BSB)</span><br>${ctx.bsb}</p>` : ""}
    <div class="ws-nav">
      <button type="button" class="btn secondary" data-step="-1" ${ctx.i === 0 ? "disabled" : ""}>Previous word</button>
      <button type="button" class="btn secondary" data-step="1" ${ctx.i >= ctx.n - 1 ? "disabled" : ""}>Next word</button>
    </div>
    <p class="muted ws-soon">Every place this word appears, in the dictionary, comes in a later update.</p>`;
}

function wordSheetHTML(w, ctx) {
  const [text, translit, english, strong = "", morph = "", after = "", before = ""] = w;
  const keys = strong.split("+").filter(Boolean);
  const codes = morph.split("+").filter(Boolean);
  const lex = keys.map((k) => ctx.lex[k] || [text, translit, ""]);
  const grammar = codes.map((c) => ctx.morph[c] || [c]);
  const form = esc(text);
  return `
    <p class="ws-ref">${esc(ctx.ref)}</p>
    <h2 class="ws-word" lang="grc" id="sheet-title">${form}</h2>
    <p class="ws-translit">${esc(translit)}</p>
    <dl class="ws-facts">
      <div><dt>Dictionary form</dt><dd>${lex.map((l, i) => `<span lang="grc" class="ws-lemma">${esc(l[0])}</span> <span class="muted">${esc(l[1])} · Strong's ${esc(strongs(keys[i]))}</span>`).join("<br>")}</dd></div>
      <div><dt>Meaning</dt><dd>${lex.map((l) => esc(compact(l[2]) || "—")).join(" + ")}</dd></div>
      <div><dt>In this verse</dt><dd>${englishHTML(english) || "—"}</dd></div>
      <div><dt>Grammar</dt><dd>${grammar.map((g) => `<strong>${esc(friendlyGrammar(g[0]))}</strong>${g[1] ? `<span class="ws-explain">${esc(g[1])}${g[2] ? `, as in “${esc(g[2])}”` : ""}.</span>` : ""}`).join("<br>")}</dd></div>
      <div class="ws-count" hidden><dt>How common</dt><dd></dd></div>
    </dl>
    ${ctx.bsb ? `<p class="ws-bsb"><span class="muted">${esc(ctx.bsbRef)} (BSB)</span><br>${ctx.bsb}</p>` : ""}
    <div class="ws-nav">
      <button type="button" class="btn secondary" data-step="-1" ${ctx.i === 0 ? "disabled" : ""}>Previous word</button>
      <button type="button" class="btn secondary" data-step="1" ${ctx.i >= ctx.n - 1 ? "disabled" : ""}>Next word</button>
    </div>
    <p class="muted ws-soon">Every place this word appears, in the dictionary, comes in a later update.</p>`;
}

function showWord(state, vi, wi, returnFocus) {
  const verse = state.verses[vi];
  const w = verse[1][wi];
  const name = state.book.id === "PSA" ? "Psalm" : state.book.name;
  const heRef = state.he && typeof verse[2] === "string" ? ` (Hebrew Bible ${refLabel(verse[2])})` : "";
  const where = verse[0] === 0 ? `${name} ${state.ch}, title` : `${name} ${state.ch}:${verse[0]}`;
  const ref = `${where}${heRef}`;
  const refs = englishRefs(state, verse);
  const own = refs.length === 1 && refs[0] === `${state.ch}.${verse[0]}`;
  const bsb = refs.map((r) => bsbVerse(state, r)).filter(Boolean)
    .map((b) => (own ? "" : `<sup class="bsb-ref">${b.c === state.ch ? b.n : `${b.c}:${b.n}`}</sup>`) + bsbHTML(b.text, b.notes, b.c))
    .join(" ").replace(/<button[^>]*>†<\/button>/g, "");
  const ctx = {
    lex: state.lex, morph: state.morph, ref, i: wi, n: verse[1].length, bsb,
    bsbRef: own ? where : `${name} ${refs.map(refLabel).join(", ")}`,
  };
  const body = openSheet(state.he ? heWordSheetHTML(w, ctx) : wordSheetHTML(w, ctx),
    { label: `Word details: ${state.he ? heText(w) : w[0]}`, returnFocus });
  document.querySelectorAll(".w.on").forEach((el) => el.classList.remove("on"));
  const el = document.querySelector(`.v[data-vi="${vi}"] .w[data-wi="${wi}"]`);
  el?.classList.add("on");
  body.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
    const next = wi + Number(b.dataset.step);
    const target = document.querySelector(`.v[data-vi="${vi}"] .w[data-wi="${next}"]`);
    showWord(state, vi, next, target || returnFocus);
    target?.scrollIntoView({ block: "nearest" });
  }));
  wordCounts(state.he).then((m) => {
    const key = state.he ? heMainKey(w) : String(w[3] || "").split("+")[0];
    const n = m.get(key);
    const row = body.querySelector(".ws-count");
    const where = state.he ? "Old Testament" : "New Testament";
    if (row && n && realStrongs(key)) {
      row.hidden = false;
      row.querySelector("dd").textContent = n === 1 ? `Only here in the ${where}` : `${n.toLocaleString("en-GB")} times in the ${where}`;
    }
  }).catch(() => {});
}

// ---------------------------------------------------------------- chapter rendering

/** "and + the + noun fs"; the "and" of a wayyiqtol is part of that verb form, so it isn't repeated. */
function heWordGrammar(w, morph) {
  const labels = heParts(w).map((p) => heShortGrammar((morph[p.code] || [p.code])[0]));
  return labels.filter((l, i) => !(l === "and (narrative)" && /wayyiqtol/.test(labels[i + 1] || ""))).join(" + ");
}

function heWordHTML(w, vi, wi, state) {
  const [, translit, english, , , after = "", flag = ""] = w;
  let he = esc(heText(w));
  if (flag === "x") he = `[${he}]`;
  if (flag === "q") he += `<span class="q-mark" aria-hidden="true">°</span>`;
  he += esc(heAfter(after));
  const cls = `w${flag ? ` w-${flag}` : ""}`;
  if (state.prefs.readLayout === "text") {
    return `<span class="${cls}" role="button" tabindex="0" data-wi="${wi}" lang="he">${he}</span>`;
  }
  const grammar = state.prefs.showGrammar ? heWordGrammar(w, state.morph) : "";
  return `<span class="${cls}" role="button" tabindex="0" data-wi="${wi}">` +
    `<span class="wg" lang="he">${he}</span>` +
    (state.prefs.showTranslit ? `<span class="wt" dir="ltr">${esc(heTranslit(translit))}</span>` : "") +
    (state.prefs.showEnglish ? `<span class="we" dir="ltr">${englishHTML(heEnglish(english)) || "&nbsp;"}</span>` : "") +
    (grammar ? `<span class="wm" dir="ltr">${esc(grammar)}</span>` : "") +
    `</span>`;
}

function wordHTML(w, vi, wi, state) {
  if (state.he) return heWordHTML(w, vi, wi, state);
  const [text, translit, english, , morph = "", after = "", before = ""] = w;
  const grammar = state.prefs.showGrammar
    ? morph.split("+").map((c) => shortGrammar((state.morph[c] || [c])[0])).join(" + ") : "";
  const greek = `${esc(before)}${esc(text)}${esc(after.replace(MARKS, ""))}`;
  if (state.prefs.readLayout === "text") {
    return `<span class="w" role="button" tabindex="0" data-wi="${wi}" lang="grc">${greek}</span>`;
  }
  return `<span class="w" role="button" tabindex="0" data-wi="${wi}">` +
    `<span class="wg" lang="grc">${greek}</span>` +
    (state.prefs.showTranslit ? `<span class="wt">${esc(translit)}</span>` : "") +
    (state.prefs.showEnglish ? `<span class="we">${englishHTML(english) || "&nbsp;"}</span>` : "") +
    (grammar ? `<span class="wm">${esc(grammar)}</span>` : "") +
    `</span>`;
}

function headingsHTML(state, v) {
  return (state.bsb.headings.get(v) || []).map((h) => `<h2 class="sec">${esc(h)}</h2>`).join("");
}

const BRACKET_NOTE = `<p class="v-gap v-note">Words in double brackets [[ ]] are not in the oldest manuscripts. The NA28 editors print them because they were added very early and have long been read in the church.</p>`;

function missingNote(from, to) {
  const list = from === to ? `Verse ${from} is` : `Verses ${from} to ${to} are`;
  return `<p class="v-gap">${list} not in the oldest manuscripts, so the NA28 text and the BSB leave ${from === to ? "it" : "them"} out. The BSB footnote nearby gives the wording found in later manuscripts.</p>`;
}

/** "4–49", "11", "8–24" from a sorted list of verse numbers. */
function ranges(nums) {
  const out = [];
  nums.forEach((n) => {
    const last = out[out.length - 1];
    if (last && n === last[1] + 1) last[1] = n;
    else out.push([n, n]);
  });
  return out.map(([a, b]) => (a === b ? `${a}` : `${a} to ${b}`));
}

/** Notes for a Hebrew chapter, each placed before the first verse it concerns: vi → [html]. */
function hebrewNotes(state) {
  const notes = new Map();
  const add = (vi, html) => notes.set(vi, (notes.get(vi) || []).concat(html));
  const aramaic = state.verses.filter((v) => v[1].some(isAramaic));
  if (aramaic.length) {
    const first = state.verses.indexOf(aramaic[0]);
    const which = aramaic.length === state.verses.length ? "This chapter is"
      : `${aramaic.length === 1 ? "Verse" : "Verses"} ${ranges(aramaic.map((v) => v[0])).join(" and ")} ${aramaic.length === 1 ? "is" : "are"}`;
    add(first, `<p class="v-gap v-note">${which} in Aramaic, a sister language of Hebrew that was spoken across the Persian empire. Tap a word to see its Aramaic grammar.</p>`);
  }
  const firstWith = (flag) => state.verses.findIndex((v) => v[1].some((w) => w[6] === flag));
  const q = firstWith("q");
  if (q >= 0) add(q, `<p class="v-gap v-note">A small ° after a word means the scribes wrote it one way but marked it to be read aloud another way. You see the way it is read; tap the word to see how it is written.</p>`);
  const k = firstWith("k");
  if (k >= 0) add(k, `<p class="v-gap v-note">Words in grey are written in the Hebrew text but, by long tradition, not read aloud.</p>`);
  const x = firstWith("x");
  if (x >= 0) add(x, `<p class="v-gap v-note">Words in square brackets are missing from the Leningrad Codex and are supplied from other manuscripts.</p>`);
  return notes;
}

function chapterHTML(state) {
  if (state.he) return heChapterHTML(state);
  const out = [];
  const assigned = new Set();
  // An English verse goes under the NA28 verse with the same number when that verse holds any of its words,
  // otherwise under the first NA28 verse that holds them (e.g. 2 Cor 13:14 under NA28 13:13).
  const owner = new Map();
  state.verses.forEach((verse, vi) => {
    const own = `${state.ch}.${verse[0]}`;
    if (englishRefs(state, verse).includes(own)) owner.set(own, vi);
  });
  const textMode = state.prefs.readLayout === "text";
  let prev = 0;
  let para = [];
  const flushPara = () => { if (para.length) { out.push(`<p class="para" lang="grc">${para.join(" ")}</p>`); para = []; } };

  state.verses.forEach((verse, vi) => {
    const [v, words] = verse;
    if (v > prev + 1 && prev > 0) { flushPara(); out.push(missingNote(prev + 1, v - 1)); }
    prev = v;
    const heads = headingsHTML(state, v);
    if (textMode) {
      if (heads) { flushPara(); out.push(heads); }
      if (!state.bracketNoted && words.some((w) => String(w[6] || "").includes("[["))) {
        state.bracketNoted = true;
        flushPara(); out.push(BRACKET_NOTE);
      }
      let run = `<sup class="vn"><span class="sr">Verse </span>${v}</sup>`;
      let first = true;
      const push = () => { para.push(`<span class="v" data-vi="${vi}"${first ? ` id="v${v}"` : ""}>${run}</span>`); first = false; run = ""; };
      words.forEach((w, wi) => {
        run += (wi ? " " : "") + wordHTML(w, vi, wi, state);
        if (String(w[5] || "").includes("¶")) { push(); flushPara(); } // ¶ = paragraph break in the Greek text
      });
      if (run) push();
      return;
    }
    out.push(heads);
    if (!state.bracketNoted && words.some((w) => String(w[6] || "").includes("[["))) {
      state.bracketNoted = true;
      out.push(BRACKET_NOTE);
    }
    const refs = englishRefs(state, verse);
    const fresh = refs.filter((r) => (owner.has(r) ? owner.get(r) === vi : !assigned.has(r)));
    fresh.forEach((r) => assigned.add(r));
    const own = fresh.length === 1 && fresh[0] === `${state.ch}.${v}`;
    const parts = fresh.map((r) => bsbVerse(state, r)).filter(Boolean)
      .map((b) => (own ? "" : `<sup class="bsb-ref">${b.c === state.ch ? b.n : `${b.c}:${b.n}`}</sup>`) + bsbHTML(b.text, b.notes, b.c));
    const bsb = !state.prefs.showBSB ? ""
      : parts.length ? `<p class="bsb">${parts.join(" ")}</p>`
      : `<p class="bsb muted">In the BSB these words are part of ${refs.map((r) => (r.startsWith(`${state.ch}.`) ? `verse ${r.split(".")[1]}` : refLabel(r))).join(" and ")}.</p>`;
    out.push(`<div class="v" data-vi="${vi}" id="v${v}"><span class="vn"><span class="sr">Verse </span>${v}</span><div class="words" lang="grc">${words.map((w, wi) => wordHTML(w, vi, wi, state)).join("")}</div>${bsb}</div>`);
  });
  flushPara();

  // Any BSB verse in this chapter that no NA28 verse covered (none expected; kept as a safety net)
  if (state.prefs.showBSB && !textMode) {
    for (const [v, text] of state.bsb.verses) {
      if (v > 0 && text && !assigned.has(`${state.ch}.${v}`) && v > prev) {
        out.push(`<div class="v v-bsb-only"><span class="vn">${v}</span><p class="bsb">${bsbHTML(text, state.bsb.notes, state.ch)}</p></div>`);
      }
    }
  }
  return out.join("");
}

/** A Hebrew chapter. Verse numbers follow English Bibles (as the BSB does); the Hebrew number is shown where it differs. */
function heChapterHTML(state) {
  const out = [];
  const notes = hebrewNotes(state);
  const textMode = state.prefs.readLayout === "text";
  const aramaicVerses = state.verses.filter((v) => v[1].some(isAramaic)).length;
  const mixed = aramaicVerses > 0 && aramaicVerses < state.verses.length;
  let para = [];
  const flushPara = () => { if (para.length) { out.push(`<p class="para" lang="he" dir="rtl">${para.join("")}</p>`); para = []; } };

  state.verses.forEach((verse, vi) => {
    const [v, words, heRef] = verse;
    const before = headingsHTML(state, v) + (notes.get(vi) || []).join("");
    if (textMode) {
      if (before || v === 0) flushPara();
      if (before) out.push(before);
      let run = v === 0 ? "" : `<sup class="vn"><span class="sr">Verse </span>${v}</sup>`;
      let first = true;
      const push = () => { para.push(`<span class="v" data-vi="${vi}"${first ? ` id="v${v}"` : ""}>${run}</span>`); first = false; run = ""; };
      words.forEach((w, wi) => {
        run += wordHTML(w, vi, wi, state) + (heJoined(w[5]) ? "" : " ");
        if (heParagraphAfter(w[5])) { push(); flushPara(); } // פ and ס mark paragraph breaks in the Hebrew text
      });
      if (run) push();
      if (v === 0) flushPara(); // a psalm's title stands on its own
      return;
    }
    out.push(before);
    const text = state.bsb.verses.get(v);
    const bsb = state.prefs.showBSB && text ? `<p class="bsb" dir="ltr" lang="en">${bsbHTML(text, state.bsb.notes, state.ch)}</p>` : "";
    const heNum = typeof heRef === "string"
      ? `<span class="vh" dir="ltr" title="Verse number in Hebrew Bibles"><span class="sr">, Hebrew Bible </span><span aria-hidden="true">Heb </span>${refLabel(heRef)}</span>` : "";
    const aram = mixed && words.some(isAramaic) ? `<span class="vh" dir="ltr">Aram.</span>` : "";
    const vn = v === 0 ? `<span class="vn vn-title">title${heNum}</span>` : `<span class="vn"><span class="sr">Verse </span>${v}${heNum}${aram}</span>`;
    out.push(`<div class="v" data-vi="${vi}" id="v${v}" dir="rtl">${vn}<div class="words" lang="he">${words.map((w, wi) => wordHTML(w, vi, wi, state)).join("")}</div>${bsb}</div>`);
  });
  flushPara();
  return out.join("");
}

// ---------------------------------------------------------------- pickers and display options

function pickerHTML(books, current, testament) {
  const byId = Object.fromEntries(books.map((b) => [b.id, b]));
  const tab = (t, label) => `<button type="button" data-testament="${t}" aria-pressed="${t === testament}">${label}</button>`;
  return `<h2 class="sheet-title">Choose a book</h2>
    <div class="switch pick-switch" role="group" aria-label="Testament">${tab("OT", "Old Testament")}${tab("NT", "New Testament")}</div>
    <p class="muted pick-lang">${testament === "OT" ? "In Hebrew, with a few chapters in Aramaic" : "In Greek"}</p>
    ${GROUPS[testament].map(([name, ids]) => `
      <h3 class="pick-group">${name}</h3>
      <div class="pick-books">${ids.filter((id) => byId[id]).map((id) => `<button type="button" class="pick-book" data-book="${id}" ${id === current ? 'aria-current="true"' : ""}>${esc(byId[id].name)}</button>`).join("")}</div>`).join("")}`;
}

function chaptersHTML(book) {
  return `<h2 class="sheet-title">${esc(book.name)}</h2>
    <p class="muted" style="margin-top:-6px">Choose a chapter</p>
    <div class="pick-chapters">${Array.from({ length: book.ch }, (_, i) => `<a class="pick-ch" href="#/read/${book.id}/${i + 1}">${i + 1}</a>`).join("")}</div>
    <p><button type="button" class="btn secondary" data-back>All books</button></p>`;
}

function displayHTML(prefs) {
  const box = (key, label, help = "") => `<label class="toggle"><input type="checkbox" data-pref="${key}" ${prefs[key] ? "checked" : ""}><span><strong>${label}</strong>${help ? `<span class="muted">${help}</span>` : ""}</span></label>`;
  return `<h2 class="sheet-title">Display</h2>
    <fieldset>
      <legend>Layout</legend>
      <div class="choices">
        <label><input type="radio" name="readLayout" value="words" ${prefs.readLayout === "words" ? "checked" : ""}> Word by word</label>
        <label><input type="radio" name="readLayout" value="text" ${prefs.readLayout === "text" ? "checked" : ""}> Running text</label>
      </div>
      <p class="field-help">Running text shows the Hebrew or Greek on its own, like a reader's edition. Tap any word for help.</p>
    </fieldset>
    <fieldset class="word-opts" ${prefs.readLayout === "text" ? "disabled" : ""}>
      <legend>Under each word</legend>
      ${box("showEnglish", "English meaning")}
      ${box("showTranslit", "Pronunciation", "Letters spelt out in English. In Hebrew, the syllable with a capital letter is stressed.")}
      ${box("showGrammar", "Grammar", "Greek: e.g. noun nom. sg. masc. Hebrew: e.g. Qal pf. 3ms (3ms = he; 3fs = she; 1cs = I; cstr. = “of”).")}
    </fieldset>
    <fieldset class="word-opts" ${prefs.readLayout === "text" ? "disabled" : ""}>
      <legend>Under each verse</legend>
      ${box("showBSB", "Berean Standard Bible")}
    </fieldset>`;
}

// ---------------------------------------------------------------- the screen

function prefsNow() {
  return Object.fromEntries(["readLayout", "showEnglish", "showTranslit", "showGrammar", "showBSB"].map((k) => [k, store.get(k)]));
}

export const read = {
  title: "Read",
  handlesTitle: true,
  handlesScroll: true,
  async render(main, params = []) {
    const books = await data.books().catch(() => null);
    const bible = (books || []).filter((b) => b.lang === "grc" || b.lang === "he");
    let [bookId, chStr, vStr] = params;
    if (!bookId) [bookId, chStr] = String(store.get("lastRead")).split("/");
    bookId = String(bookId || "JHN").toUpperCase();
    const book = (books || []).find((b) => b.id === bookId);
    const ch = Math.max(1, Math.min(Number(chStr) || 1, book?.ch || 1));

    if (!books) {
      main.innerHTML = `<div class="screen"><header class="screen-head"><div><h1>Read</h1></div></header>
        <div class="note"><p>The Bible text couldn't load. Connect to the internet once and it will be saved for offline reading.</p></div></div>`;
      return;
    }
    if (!book || !bible.includes(book)) {
      main.innerHTML = `<div class="screen"><header class="screen-head"><div><h1>Read</h1></div></header>
        <div class="note"><p>That book wasn't found. Choose one to read.</p></div>
        <p><a class="btn" href="#/read/GEN/1">Open Genesis 1</a> <a class="btn secondary" href="#/read/JHN/1">Open John 1</a></p></div>`;
      document.title = "Read · Aleph to Omega";
      return;
    }
    const he = book.lang === "he";

    const idx = bible.indexOf(book);
    const prevRef = ch > 1 ? [book, ch - 1] : idx > 0 ? [bible[idx - 1], bible[idx - 1].ch] : null;
    const nextRef = ch < book.ch ? [book, ch + 1] : idx < bible.length - 1 ? [bible[idx + 1], 1] : null;
    const link = (r) => `#/read/${r[0].id}/${r[1]}`;
    const label = (r) => chapterName(r[0], r[1]);
    const title = chapterName(book, ch);

    document.title = `${title} · Aleph to Omega`;
    store.set("lastRead", `${book.id}/${ch}`);
    main.innerHTML = `<div class="screen reader">
      <header class="reader-head">
        <h1 class="reader-h1"><button type="button" class="reader-title" data-pick aria-haspopup="dialog" aria-label="${esc(title)}, choose another chapter">
          <span class="rt-name">${esc(title)}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10l5 5 5-5"/></svg>
        </button></h1>
        <div class="reader-tools">
          ${prevRef ? `<a class="icon-btn" href="${link(prevRef)}" aria-label="Previous chapter: ${esc(label(prevRef))}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></a>` : ""}
          ${nextRef ? `<a class="icon-btn" href="${link(nextRef)}" aria-label="Next chapter: ${esc(label(nextRef))}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></a>` : ""}
          <button type="button" class="icon-btn" data-display aria-haspopup="dialog" aria-label="Display options"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg></button>
        </div>
      </header>
      <p class="reader-source">${he ? "Hebrew and Aramaic Old Testament (Leningrad Codex)" : "Greek New Testament (NA28 text)"} with the Berean Standard Bible</p>
      <div class="chapter" aria-busy="true"><p class="muted">Loading ${esc(title)}…</p></div>
      <nav class="chapter-nav" aria-label="Chapters">
        ${prevRef ? `<a class="btn secondary" href="${link(prevRef)}">${esc(label(prevRef))}</a>` : "<span></span>"}
        ${nextRef ? `<a class="btn secondary" href="${link(nextRef)}">${esc(label(nextRef))}</a>` : ""}
      </nav>
    </div>`;
    if (!vStr) window.scrollTo(0, 0);

    const holder = main.querySelector(".chapter");
    let original, bsbBook, morph;
    try {
      [original, bsbBook, morph] = await Promise.all([data.original(book.id), data.bsb(book.id), data.morph(he ? "he" : "grc")]);
    } catch {
      holder.innerHTML = `<div class="note"><p>${esc(book.name)} couldn't load. Connect to the internet once and it will be saved for offline reading.</p></div>`;
      holder.removeAttribute("aria-busy");
      return;
    }
    if (!main.contains(holder)) return; // moved on while loading
    const chapter = original.ch.find(([c]) => c === ch);
    const state = {
      book, ch, he, lex: original.lex, morph, prefs: prefsNow(), bsbBook, other: {},
      verses: chapter ? chapter[1] : [], bsb: bsbChapter(bsbBook, ch),
    };
    const draw = () => {
      state.bracketNoted = false;
      holder.className = `chapter layout-${state.prefs.readLayout}${he ? " lang-he" : ""}`;
      holder.innerHTML = chapterHTML(state);
      holder.removeAttribute("aria-busy");
    };
    draw();

    if (vStr) {
      const target = holder.querySelector(`#v${Number(vStr)}`);
      if (target) {
        target.classList.add("focus");
        target.scrollIntoView({ block: "center" });
      }
    }

    // word taps (one listener for the whole chapter)
    const pick = (el) => {
      const w = el.closest(".w");
      const v = el.closest("[data-vi]");
      if (w && v) showWord(state, Number(v.dataset.vi), Number(w.dataset.wi), w);
    };
    holder.addEventListener("click", (e) => {
      const fn = e.target.closest(".fn");
      if (fn) {
        const [c, i] = fn.dataset.note.split(":").map(Number);
        const notes = c === ch ? state.bsb.notes : bsbChapter(bsbBook, c).notes;
        openSheet(`<h2 class="sheet-title">Translator's note</h2><p>${esc(notes[i])}</p><p class="muted">From the Berean Standard Bible.</p>`, { label: "Translator's note", returnFocus: fn });
        return;
      }
      if (e.target.closest(".w")) pick(e.target);
    });
    holder.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.closest(".w")) { e.preventDefault(); pick(e.target); }
    });

    // book and chapter picker
    const openPicker = (returnFocus) => {
      let testament = he ? "OT" : "NT";
      const body = openSheet(pickerHTML(bible, book.id, testament), { label: "Choose a book and chapter", returnFocus });
      body.addEventListener("click", (e) => {
        const t = e.target.closest("[data-testament]");
        if (t) {
          testament = t.dataset.testament;
          body.innerHTML = pickerHTML(bible, book.id, testament);
          body.querySelector(`[data-testament="${testament}"]`)?.focus();
          return;
        }
        const b = e.target.closest("[data-book]");
        if (b) {
          body.innerHTML = chaptersHTML(books.find((x) => x.id === b.dataset.book));
          body.querySelector(".pick-ch")?.focus();
        }
        if (e.target.closest("[data-back]")) body.innerHTML = pickerHTML(bible, book.id, testament);
        if (e.target.closest(".pick-ch")) closeSheet();
      });
    };
    main.querySelector("[data-pick]").addEventListener("click", (e) => openPicker(e.currentTarget));

    // display options: apply at once, keep the reader's place
    main.querySelector("[data-display]").addEventListener("click", (e) => {
      const body = openSheet(displayHTML(state.prefs), { label: "Display options", returnFocus: e.currentTarget });
      body.addEventListener("change", (ev) => {
        const t = ev.target;
        if (t.dataset.pref) store.set(t.dataset.pref, t.checked);
        if (t.name === "readLayout") store.set("readLayout", t.value);
        state.prefs = prefsNow();
        body.querySelectorAll(".word-opts").forEach((f) => (f.disabled = state.prefs.readLayout === "text"));
        const anchor = [...holder.querySelectorAll(".v")].find((v) => v.getBoundingClientRect().bottom > 80);
        draw();
        if (anchor?.id) holder.querySelector(`#${anchor.id}`)?.scrollIntoView({ block: "start" });
      });
    });
  },
};
