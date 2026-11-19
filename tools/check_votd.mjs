// Today's verse check (19 Nov 2026):  node tools/check_votd.mjs
//
// Builds every verse in data/votd-pool.json exactly as Today does (js/votd.js buildVerse) and checks it:
//   • the pool: every ref is a real verse with words and BSB English, in Reader numbering, no duplicates;
//   • every word: the text as the Reader shows it, its English here, dictionary form, meaning, grammar and dictionary
//     key; a Greek word joined from two (κἀγώ) carries both parts; Hebrew prefixes carry their own dictionary form;
//   • the voice: "Listen to the verse" says the Reader's verse text (audio.verseSpeech), each tapped word says what the
//     Reader's word sheet says (audio.heVoice for Hebrew), and the words said in the verse are the words tapped;
//   • the English: a whole sentence, no headings, cross-references, note markers or brackets;
//   • the daily pick: a full cycle of days shows every verse once (no repeats), Greek and Hebrew differ, and the
//     first ten days are spread over several books (a shuffle, not Bible order);
//   • the fallback verses (data/votd.json, used when a book can't load): their spoken text is the Reader's too.
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const R = path.join(path.dirname(fileURLToPath(import.meta.url)), "..") + "/";
const V = await import(R + "js/votd.js");
const audio = await import(R + "js/audio.js");
const H = await import(R + "js/hebrew.js");
const S = await import(R + "js/sound.js");
const json = (f) => JSON.parse(fs.readFileSync(R + f, "utf8"));
const problems = [];
const bad = (kind, detail) => problems.push([kind, detail]);

const books = json("data/books.json");
const order = books.map((b) => b.id);
const pool = json("data/votd-pool.json");
const morph = { grc: json("data/morph/greek.json"), he: json("data/morph/hebrew.json") };
const cache = {};
const book = (id) => {
  if (!cache[id]) {
    const b = books.find((x) => x.id === id);
    cache[id] = { b, orig: json(`data/${b.lang === "grc" ? "gnt" : "hot"}/${id}.json`), bsb: json(`data/bsb/${id}.json`) };
  }
  return cache[id];
};

/** The Reader's BSB verse text (js/reader.js bsbChapter, without DOM). */
function bsbVerse(bsbBook, ch, v) {
  const chapter = bsbBook.chapters[ch - 1];
  if (!chapter) return "";
  let cur = 0;
  const out = new Map();
  for (const [kind, items] of chapter[0]) {
    if (kind === "s" || kind === "qa" || kind === "r" || kind === "b") continue;
    for (const x of items) {
      if (typeof x === "number") { cur = x; if (!out.has(cur)) out.set(cur, ""); }
      else if (typeof x === "string") out.set(cur, ((out.get(cur) || "") + " " + x).replace(/\s+/g, " ").trim());
    }
  }
  return out.get(v) || "";
}

let built = 0;
const counts = {};
for (const lang of ["grc", "he"]) {
  const refs = V.poolRefs(pool, lang, order);
  counts[lang] = refs.length;
  if (refs.length !== pool.count[lang]) bad("pool", `${lang}: ${refs.length} refs but count says ${pool.count[lang]}`);
  const seen = new Set();
  for (const [id, ch, v] of refs) {
    const key = `${id} ${ch}:${v}`;
    if (seen.has(key)) bad("pool", `${key} listed twice`);
    seen.add(key);
    const { b, orig, bsb } = book(id);
    if ((b.lang === "grc" ? "grc" : "he") !== lang) { bad("pool", `${key} is in the wrong language's list`); continue; }
    const item = ((orig.ch.find(([c]) => c === ch) || [0, []])[1].find(([n]) => n === v));
    if (!item || !item[1].length) { bad("pool", `${key}: no such verse in the data`); continue; }
    const words = item[1];
    const english = bsbVerse(bsb, ch, v);
    const verse = V.buildVerse({ lang, bookId: id, ch, v, name: b.name, words, lex: orig.lex, morph: morph[lang], english });
    built++;
    // the words
    if (verse.words.length !== words.length) bad("words", `${key}: ${verse.words.length} words built from ${words.length}`);
    verse.words.forEach((w, i) => {
      const src = words[i];
      for (const f of ["t", "en", "lemma", "gloss", "parse", "k"]) if (!String(w[f] || "").trim()) bad(`word without ${f}`, `${key} ${w.t || i}`);
      if (/\bundefined\b|\bnull\b|\bNaN\b|\[object/.test(JSON.stringify(w))) bad("odd text in a word", `${key} ${w.t}`);
      const shown = lang === "he" ? H.heText(src) : src[0];
      if (w.t !== shown) bad("word differs from the Reader", `${key}: ${w.t} ≠ ${shown}`);
      if (lang === "grc" && String(src[3]).includes("+") && !(w.parts && w.parts.length === String(src[3]).split("+").length && w.parts.every((p) => p[0] && p[1] && p[2])))
        bad("joined word without both parts", `${key} ${w.t}`);
      if (lang === "he") {
        const parts = H.heParts(src).filter((p) => !p.main);
        // a prefix or ending names its own dictionary form and meaning: Preposition ב “in/on/with”
        const described = (w.parse.match(/“[^”]+”/g) || []).length;
        if (described < parts.length) bad("Hebrew prefix or ending without its meaning", `${key} ${w.t}: ${w.parse}`);
        const said = audio.heVoice(src, H.heText(src), H.heJoined(src[5]), orig.lex) + (H.heJoined(src[5]) ? "־" : "");
        if (w.say !== said) bad("tapped word not said as in the Reader", `${key} ${w.t}`);
      } else if (w.say !== src[0]) bad("tapped word not said as in the Reader", `${key} ${w.t}`);
      if (lang === "grc" && w.p !== String(src[5] || "").replace(/[¶¬]/g, "")) bad("punctuation differs from the Reader", `${key} ${w.t}`);
    });
    if (!(verse.focus >= 0 && verse.focus < verse.words.length)) bad("focus word out of range", key);
    // the voice
    const spoken = audio.verseSpeech(words, lang, orig.lex);
    if (verse.spoken !== spoken) bad("whole verse not said as in the Reader", key);
    if (!spoken.trim()) bad("nothing to say for the verse", key);
    // the words said in the verse are the words tapped (Hebrew: what heVoice gives; words flagged k are never in the pool)
    const inVerse = spoken.replace(/[,.;:·?!—()“”’‘"[\]⟦⟧]/g, " ").replace(/[׃]/g, " ").split(/[\s־]+/).filter(Boolean).length;
    const tapped = verse.words.map((w) => w.say).join(" ").replace(/[,.;:·?!—()“”’‘"[\]⟦⟧]/g, " ").split(/[\s־]+/).filter(Boolean).length;
    if (inVerse !== tapped) bad("verse and tapped words say a different number of words", `${key}: ${inVerse} vs ${tapped}`);
    // the English
    const en = verse.english;
    if (!en) bad("no English", key);
    else {
      if (/\u0001|\(\w+ \d+:\d+|[[\]]/.test(en)) bad("English carries a note marker, cross-reference or bracket", `${key}: ${en.slice(0, 60)}`);
      if (!/^[“‘"'(]?[A-Z]/.test(en) || !/[.!?][”’"')]*$/.test(en)) bad("English isn't a whole sentence", `${key}: ${en.slice(0, 60)}`);
      if ((en.match(/“/g) || []).length !== (en.match(/”/g) || []).length) bad("English quotation marks don't pair", `${key}: ${en.slice(0, 60)}`);
      if ((en.match(/\(/g) || []).length !== (en.match(/\)/g) || []).length) bad("English brackets don't pair", `${key}: ${en.slice(0, 60)}`);
      // single quotes, read left to right: ‘ opens; ’ closes an open one unless a letter follows (Lord’s); a ’ after a
      // mark with nothing open is a quote closing that opened in another verse (…Canaan.’)
      let open = 0, stray = false;
      for (let i = 0; i < en.length; i++) {
        if (en[i] === "‘") open++;
        else if (en[i] === "’" && !/\p{L}/u.test(en[i + 1] || "")) {
          if (open) open--;
          else if (/[.,!?;:—–]/.test(en[i - 1] || "")) stray = true;
        }
      }
      if (open || stray) bad("English single quotes don't pair", `${key}: ${en.slice(0, 70)}`);
    }
    if (!new RegExp(`^${verse.ref.split(" ").slice(0, -1).join(" ").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} ${ch}:${v}$`).test(verse.ref)) bad("reference label", `${key}: ${verse.ref}`);
  }
  // the daily pick: a whole cycle with no repeats, a shuffle rather than Bible order
  const n = refs.length, start = 20000;
  const picked = new Set();
  for (let d = 0; d < n; d++) { const r = V.pickRef(refs, lang, start + d); picked.add(r.join(" ")); }
  if (picked.size !== n) bad("daily pick", `${lang}: ${picked.size} different verses over ${n} days (a verse came back early)`);
  const ten = new Set(Array.from({ length: 10 }, (_, d) => V.pickRef(refs, lang, start + d)[0]));
  if (ten.size < 4) bad("daily pick", `${lang}: ten days in a row drew from only ${ten.size} books`);
}
const same = Array.from({ length: 50 }, (_, d) => V.pickRef(V.poolRefs(pool, "grc", order), "grc", 20000 + d).join() === V.pickRef(V.poolRefs(pool, "he", order), "he", 20000 + d).join()).filter(Boolean).length;
if (same) bad("daily pick", "Greek and Hebrew picked the same verse");

// the fallback verses: what Today says for them is what the Reader says
for (const fv of json("data/votd.json")) {
  const [id, ch, v] = fv.id.split("-");
  const { orig } = book(id);
  const words = ((orig.ch.find(([c]) => c === +ch) || [0, []])[1].find(([x]) => x === +v) || [0, []])[1];
  const reader = audio.verseSpeech(words, fv.lang, orig.lex);
  const today = fv.words.map((w) => V.todayVoice(fv, w) + String(w.p || "").replace(/[¶¬]/g, ""))
    .reduce((out, t, i) => out + (i && !String(fv.words[i - 1].p || "").endsWith("־") ? " " : "") + t, "");
  const norm = (t) => (fv.lang === "he" ? S.hebrewSpeech(t) : t).replace(/\s+/g, " ").trim();
  if (norm(today) !== norm(reader)) bad("fallback verse not said as in the Reader", `${fv.ref}\n      Today:  ${norm(today).slice(0, 120)}\n      Reader: ${norm(reader).slice(0, 120)}`);
}

console.log(`Today's verse: ${counts.grc} Greek and ${counts.he} Hebrew verses in the pool, ${built} built as Today shows them.`);
if (!problems.length) {
  console.log("Every pool verse is complete, said as in the Reader, and the daily pick goes through them all without repeats.");
  process.exit(0);
}
const byKind = {};
problems.forEach(([k, d]) => (byKind[k] = byKind[k] || []).push(d));
console.log(`\n${problems.length} problems in ${Object.keys(byKind).length} kinds:`);
for (const [k, list] of Object.entries(byKind)) {
  console.log(`  ${list.length} × ${k}`);
  list.slice(0, 6).forEach((d) => console.log("      " + d));
}
process.exit(1);
