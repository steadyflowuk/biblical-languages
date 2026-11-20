// The Guide against the app (19 Nov 2026):  node tools/check_guide.mjs  [--self-test]
//
// tools/check_guide.py checks the guide's own text. This checks that the guide covers what the app shows, using the
// app's own code (js/reader.js, js/hebrew.js, js/guide-text.js, js/votd.js, js/audio.js):
//   labels      every grammar code used in the Bible (≈1,900), as the app shows it in full, reads into terms that
//               all have an entry (“What do these words mean?” never shows a word with no explanation)
//   short       every short label under a word (with Grammar on in the Reader) is made only of abbreviations listed
//               on the Abbreviations page, words with an entry, and person-gender-number codes such as 3ms; and every
//               Greek abbreviation the page lists is the one the app really uses for that word
//   samples     STEPBible's sample phrase shown with a label (“as in …”) has the person and number of the code
//               (its Hebrew pronoun endings once had singular and plural swapped)
//   tidy        no label shows a glue word twice in a row (“Adverb or and particle” once lost a word)
//   voices      every Greek and Hebrew word in the guide's text can be said, Hebrew as the Reader says one real
//               occurrence of it; every example builds as Today builds a verse, and its word and whole-verse Listen
//               buttons say what the Reader says
//   reach       every entry can be reached: from a section, and every grammar entry from at least one label or link
import fs from "fs";
import path from "path";

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
globalThis.window = globalThis;
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {}, key: () => null, length: 0 };
globalThis.document = { addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], documentElement: { dataset: {}, setAttribute() {} }, createElement: () => ({ style: {} }), body: {} };
globalThis.location = { hash: "" };
const reader = await import(path.join(ROOT, "js/reader.js"));
const hebrew = await import(path.join(ROOT, "js/hebrew.js"));
const G = await import(path.join(ROOT, "js/guide-text.js"));
const audio = await import(path.join(ROOT, "js/audio.js"));
const votd = await import(path.join(ROOT, "js/votd.js"));
const sound = await import(path.join(ROOT, "js/sound.js"));
const load = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, f), "utf8"));

const problems = [];
const bad = (kind, msg) => problems.push([kind, msg]);

/** Every code part used in the Bible: Greek parts of A+B, Hebrew parts of H…/…/… with the language letter. */
function codesUsed() {
  const c = { grc: new Map(), he: new Map() };
  for (const dir of ["gnt", "hot"]) {
    for (const f of fs.readdirSync(path.join(ROOT, "data", dir))) {
      const d = load(`data/${dir}/${f}`);
      for (const [ch, vs] of d.ch) for (const it of vs) for (const w of it[1]) {
        if (!w[4]) continue;
        if (dir === "gnt") w[4].split("+").forEach((k) => { if (!c.grc.has(k)) c.grc.set(k, `${d.id} ${ch}:${it[0]}`); });
        else {
          const L = w[4][0];
          w[4].slice(1).split("/").filter(Boolean).forEach((s) => { if (!c.he.has(L + s)) c.he.set(L + s, `${d.id} ${ch}:${it[0]}`); });
        }
      }
    }
  }
  return c;
}

// The Abbreviations page: its table's first column, and the plain phrases it names in quotation marks.
function abbreviationsOf(guide) {
  const e = guide.entries.find((x) => x.id === "abbreviations");
  const listed = new Map();
  const phrases = new Set();
  for (const b of (e && e.body) || []) {
    if (b.table) for (const r of b.table.rows) listed.set(r[0], r[1]);
    if (b.p) for (const m of b.p.matchAll(/“([^”]+)”/g)) phrases.add(m[1]);
  }
  return { listed, phrases };
}

export function check(guide, greekMorph, hebrewMorph, used) {
  const table = G.phraseTable(guide);
  const ids = new Set(guide.entries.map((e) => e.id));
  const reached = new Set();
  const { listed, phrases } = abbreviationsOf(guide);
  const stems = new Set(guide.entries.flatMap((e) => (e.match || []).map((m) => m.split("=")[0].trim().toLowerCase()))
    .filter((m) => /^(qal|niphal|piel|pual|hiphil|hophal|hithpael|hishtaphel|tiphil|nithpael|hothpaal|peal|peil|pael|haphel|aphel|shaphel|ishtaphel|hitpeel|hitpaal|hitpael)$/.test(m)));
  const unknown = new Map();
  const shortUnknown = new Map();
  for (const [lang, morph] of [["grc", greekMorph], ["he", hebrewMorph]]) {
    for (const [code, where] of used[lang]) {
      const m = morph[code];
      if (!m) continue;
      const full = lang === "grc" ? reader.friendlyGrammar(m[0]) : hebrew.heFriendlyGrammar(m[0]);
      const l = G.codeLang(lang, code);
      for (const t of G.labelTerms(full, l, table)) {
        if (!t.id) { if (!unknown.has(`${l} ${t.text}`)) unknown.set(`${l} ${t.text}`, `${code} (${where}): “${full}”`); }
        else { reached.add(t.id); if (!ids.has(t.id)) bad("labels", `${code}: term “${t.text}” points to no entry ${t.id}`); }
      }
      if (/\b(or|and|of) (or|and|of)\b/i.test(full)) bad("tidy", `${code}: “${full}” has two joining words in a row`);
      // the short label under the word
      const short = lang === "grc" ? reader.shortGrammar(m[0]) : hebrew.heShortGrammar(m[0]);
      let rest = ` ${short} `;
      const known = [...listed.keys(), ...phrases].sort((a, b) => b.length - a.length);
      for (const k of known) rest = rest.split(` ${k} `).join("  ").split(` ${k} `).join("  ");
      // what is left: person-gender-number codes, stem names, and words the guide explains (read as a label)
      rest = rest.split(/\s+/).filter((t) => t && !/^[123]?[mfcb]?[spd]?$/.test(t) && !stems.has(t.toLowerCase())).join(" ");
      for (const t of G.labelTerms(rest, l, table)) {
        if (t.id) continue;
        if (!shortUnknown.has(t.text)) shortUnknown.set(t.text, `${code}: “${short}”`);
      }
      // the sample phrase: person and number
      sampleCheck(lang, code, m);
    }
  }
  for (const [k, ex] of unknown) bad("labels", `no entry explains “${k.split(" ").slice(1).join(" ")}” (${k.split(" ")[0]} labels), as in ${ex}`);
  for (const [k, ex] of shortUnknown) bad("short", `“${k}” under a word is neither on the Abbreviations page nor a word with an entry, as in ${ex}`);
  // each Greek abbreviation listed is what the app writes for that word
  // …and each abbreviation listed is what the app writes for a label with that word in it
  const labels = [...Object.values(greekMorph).map((m) => ["grc", m[0]]), ...Object.values(hebrewMorph).map((m) => ["he", m[0]])];
  for (const [abbr, full] of listed) {
    if (!/\.$/.test(abbr)) continue; // 3ms, wayyiqtol: explained in their own rows
    const word = full.split(" (")[0].toLowerCase();
    const withIt = labels.filter(([, d]) => d.toLowerCase().replace(/[(),:]/g, " ").replace(/\s+/g, " ").includes(word.replace(/[(),:]/g, " ")));
    if (!withIt.length) { bad("short", `the Abbreviations page lists ${abbr} = ${full}, but no label has “${word}”`); continue; }
    const writes = withIt.some(([lang, d]) => (lang === "grc" ? reader.shortGrammar(d) : hebrew.heShortGrammar(d)).split(/\s+/).join(" ").includes(abbr));
    if (!writes) bad("short", `the Abbreviations page says ${abbr} = ${full}, but the app never writes ${abbr} for it`);
  }
  // the guide's own links reach entries too
  for (const e of guide.entries) {
    const text = JSON.stringify([e.short, e.body]);
    for (const mm of text.matchAll(/\[\[([^\]|#]+)/g)) reached.add(mm[1]);
    for (const s of e.see || []) reached.add(s);
  }
  for (const s of guide.sections) for (const id of s.entries) if (!ids.has(id)) bad("reach", `section ${s.id} lists no entry ${id}`);
  const grammarSections = new Set(["basics", "greek-nouns", "greek-verbs", "hebrew-nouns", "hebrew-verbs", "aramaic"]);
  for (const e of guide.entries) {
    if (grammarSections.has(e.section) && !reached.has(e.id)) bad("reach", `${e.id}: no label, link or “see also” leads to it (only its section list)`);
  }
  return reached;
}

const PRON = [[/^(i|me|my|myself)$/, 1, "s"], [/^(we|us|our|ourselves)$/, 1, "p"], [/^(he|him|his|himself|she|her|herself|it|its)$/, 3, "s"],
  [/^(they|them|their|themselves)$/, 3, "p"]];
function sampleCheck(lang, code, m) {
  const sample = String(m[2] || "").toLowerCase();
  if (!sample) return;
  let p = "", n = "";
  if (lang === "grc") { const mm = code.match(/-([123])([SP])(-|$)/); if (!mm || !/^V-/.test(code)) return; p = mm[1]; n = mm[2].toLowerCase(); }
  else { const mm = code.match(/^[HA](?:V..|Sp|Pp)([123])[mfcb]([sp])$/); if (!mm) return; p = mm[1]; n = mm[2]; }
  if (/\bparticiple|infinitive\b/i.test(m[0])) return;
  const words = sample.split(/[^a-z]+/).filter(Boolean);
  for (const w of words) {
    for (const [rx, pp, nn] of PRON) {
      if (rx.test(w) && (String(pp) !== p || nn !== n)) {
        bad("samples", `${code} (${p}${n}): the sample “${m[2]}” says “${w}”`);
        return;
      }
    }
    if (/^(you|your)$/.test(w) && p !== "2") { bad("samples", `${code} (${p}${n}): the sample “${m[2]}” says “${w}”`); return; }
  }
}

function voices(guide, ex) {
  const byId = Object.fromEntries(guide.entries.map((e) => [e.id, e]));
  let words = 0;
  for (const e of guide.entries) {
    const texts = [e.short, ...(e.body || []).flatMap((b) => (b.p ? [b.p] : b.h ? [b.h] : b.ul ? b.ul : b.table ? [b.table.caption, ...b.table.head, ...b.table.rows.flat()] : []))];
    for (const t of texts) {
      for (const w of G.originalWords(t)) {
        if (w.part) continue;
        words++;
        const html = G.renderText(w.word, { entries: byId, books: guide.books, voices: ex.words });
        const say = (html.match(/data-say="([^"]*)"/) || [])[1];
        if (!say) { bad("voices", `${e.id}: ${w.word} has no Listen`); continue; }
        if (!audio.sayButton(say.replace(/&#39;/g, "'").replace(/&amp;/g, "&"), w.lang)) bad("voices", `${e.id}: ${w.word}: nothing a voice could say (“${say}”)`);
        if (w.lang === "he" && /[֑-֯]/.test(sound.speechText(ex.words[w.word] ? audio.heVoice(ex.words[w.word][0], w.word, false, ex.words[w.word][1]) : w.word, "he"))) {
          bad("voices", `${e.id}: ${w.word}: accent marks left in what the voice is given`);
        }
      }
    }
  }
  let built = 0;
  const morph = { grc: load("data/morph/greek.json"), he: load("data/morph/hebrew.json") };
  for (const [id, list] of Object.entries(ex.examples)) {
    for (const x of list) {
      const v = votd.buildVerse({ lang: x.lang, bookId: x.book, ch: x.ch, v: x.v, name: "", words: x.words, lex: x.lex, morph: morph[x.lang], english: x.english });
      built++;
      const w = x.words[x.wi];
      const item = v.words[x.wi];
      const want = x.lang === "he" ? audio.heVoice(w, null, hebrew.heJoined(w[5]), x.lex) + (hebrew.heJoined(w[5]) ? "־" : "") : w[0];
      if (item.say !== want) bad("voices", `${id} ${x.ref}: the word's Listen says “${item.say}”, the Reader “${want}”`);
      if (v.spoken !== audio.verseSpeech(x.words, x.lang, x.lex)) bad("voices", `${id} ${x.ref}: “Listen to the verse” differs from the Reader's verse`);
      if (!audio.sayButton(v.spoken, x.lang)) bad("voices", `${id} ${x.ref}: nothing a voice could say for the verse`);
      const code = w[4];
      const label = x.lang === "grc" ? code.split("+").map((c) => reader.friendlyGrammar((morph.grc[c] || [c])[0])).join(" + ")
        : code.slice(1).split("/").map((p) => hebrew.heFriendlyGrammar((morph.he[code[0] + p] || [code[0] + p])[0])).join(" + ");
      if (!label || /undefined/.test(label)) bad("voices", `${id} ${x.ref}: no grammar label for ${code}`);
    }
  }
  return { words, built };
}

/** Links into the guide from the rest of the app: every #/guide/… and more("…") in js/, every Letters guide section
 * named in alphabet.js's GUIDE_LINKS, and every written lesson has guide entries for its Notice step. */
async function appLinks(guide) {
  const ids = new Set(guide.entries.map((e) => e.id));
  const sections = new Set(guide.sections.map((s) => s.id));
  let n = 0;
  for (const f of fs.readdirSync(path.join(ROOT, "js")).filter((x) => x.endsWith(".js"))) {
    const t = fs.readFileSync(path.join(ROOT, "js", f), "utf8");
    for (const m of t.matchAll(/#\/guide\/(s\/)?([a-z0-9-]+)(?=["'`\s])/g)) {
      n++;
      if (m[1] ? !sections.has(m[2]) : !ids.has(m[2]) && m[2] !== "code") bad("links", `js/${f}: #/guide/${m[1] || ""}${m[2]} goes nowhere`);
    }
    for (const m of t.matchAll(/more\("([a-z0-9-]+)"\)|\b([qkx]): "([a-z0-9-]+)"/g)) {
      const id = m[1] || m[3];
      n++;
      if (!ids.has(id)) bad("links", `js/${f}: a note links to ${id}, which is no entry`);
    }
  }
  // read GUIDE_LINKS from the source (importing alphabet.js would need a whole page around it)
  const src = fs.readFileSync(path.join(ROOT, "js/alphabet.js"), "utf8");
  const block = src.slice(src.indexOf("export const GUIDE_LINKS = {") + "export const GUIDE_LINKS = ".length);
  const A = { GUIDE_LINKS: JSON.parse(block.slice(0, block.indexOf("\n};") + 2).replace(/,\s*}$/, "}")) };
  for (const lang of ["grc", "he"]) {
    const titles = new Set(load(`lessons/alphabet/${lang}.json`).sections.map((s) => s.title));
    for (const t of titles) if (!A.GUIDE_LINKS[t]) bad("links", `Letters guide (${lang}): section “${t}” has no guide links`);
  }
  const allTitles = new Set(["grc", "he"].flatMap((l) => load(`lessons/alphabet/${l}.json`).sections.map((s) => s.title)));
  for (const [t, list] of Object.entries(A.GUIDE_LINKS)) {
    if (!allTitles.has(t)) bad("links", `alphabet.js GUIDE_LINKS: no Letters guide section “${t}”`);
    for (const [id] of list) { n++; if (!ids.has(id)) bad("links", `alphabet.js GUIDE_LINKS “${t}”: ${id} is no entry`); }
  }
  const ix = load("lessons/index.json");
  for (const lang of ["grc", "he"]) for (const x of ix[lang]) {
    if (x.file && !guide.entries.some((e) => (e.lessons || []).includes(x.id))) bad("links", `lesson ${x.id} has no guide entries for its Notice step`);
  }
  return n;
}

async function main() {
  const guide = load("guide/guide.json");
  const ex = load("guide/examples.json");
  const used = codesUsed();
  check(guide, load("data/morph/greek.json"), load("data/morph/hebrew.json"), used);
  const v = voices(guide, ex);
  const nLinks = await appLinks(guide);
  const kinds = {};
  for (const [k, m] of problems) (kinds[k] = kinds[k] || []).push(m);
  for (const [k, ms] of Object.entries(kinds)) {
    console.log(`\n${k}: ${ms.length}`);
    ms.slice(0, 60).forEach((m) => console.log("   " + m));
    if (ms.length > 60) console.log(`   … and ${ms.length - 60} more`);
  }
  console.log(`\n${used.grc.size + used.he.size} grammar codes read as the guide explains them, ${v.words} Greek and Hebrew words in the text and ${v.built} examples said, ${nLinks} links into the guide from the app.`);
  console.log(`Guide against the app: ${problems.length} problems`);
  process.exit(problems.length ? 1 : 0);
}

function selfTest() {
  const guide = load("guide/guide.json");
  const used = codesUsed();
  const gm = load("data/morph/greek.json");
  const hm = load("data/morph/hebrew.json");
  const cases = [
    ["a label word no entry explains", () => { const g = structuredClone(guide); g.entries = g.entries.filter((e) => e.id !== "optative"); return check(g, gm, hm, used); }, "labels"],
    ["an abbreviation missing from the Abbreviations page", () => { const g = structuredClone(guide); const e = g.entries.find((x) => x.id === "abbreviations"); e.body.forEach((b) => { if (b.table) b.table.rows = b.table.rows.filter((r) => r[0] !== "plupf."); }); return check(g, gm, hm, used); }, "short"],
    ["a wrong abbreviation on the page", () => { const g = structuredClone(guide); const e = g.entries.find((x) => x.id === "abbreviations"); e.body.forEach((b) => { if (b.table) b.table.rows.forEach((r) => { if (r[0] === "fut.") r[1] = "pluperfect"; }); }); return check(g, gm, hm, used); }, "short"],
    ["a sample with singular and plural swapped", () => { const h = structuredClone(hm); h.HSp3ms = [h.HSp3ms[0], h.HSp3ms[1], "they, them, their"]; return check(guide, gm, h, used); }, "samples"],
    ["a label with a dropped word", () => { const g2 = structuredClone(gm); g2["ADV-N"] = ["Adverb or and particle combined negative"]; return check(guide, g2, hm, used); }, "tidy"],
  ];
  let ok = 0;
  for (const [name, f, kind] of cases) {
    problems.length = 0;
    f();
    const caught = problems.some(([k]) => k === kind);
    console.log(`${caught ? "caught " : "MISSED "}${name}`);
    ok += caught;
  }
  console.log(`${ok}/${cases.length} passed`);
  process.exit(ok === cases.length ? 0 : 1);
}

if (process.argv.includes("--self-test")) selfTest();
else await main();
