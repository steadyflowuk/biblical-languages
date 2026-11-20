// Today's verse (19 Nov 2026): one verse a day per language, picked at random from data/votd-pool.json (some 4,900
// Greek and 9,700 Hebrew verses that read well on their own; tools/build_votd_pool.py) and built from the Bible data
// exactly as the Reader shows it, so its words, grammar and voice are the Reader's. The pick depends only on the
// date, so every device shows the same verse that day. If the book can't be loaded (offline, never opened), the
// screen falls back to data/votd.json's 24 verses, then to the built-in ones (js/verses.js).
import { heText, heAfter, heJoined, heLemma, heParts, heMainKey, hePartGloss } from "./hebrew.js";
import { heVoice, verseSpeech } from "./audio.js";

/** Today's verses from data/votd.json and js/verses.js (the fallbacks) have no Reader word arrays: */
/**
 * A Today word as the voice gets it. Hebrew: Today's words carry a description of their grammar ("Conjunction וְ
 * “and” + Verb: Qal … perfect … third singular"), not the Reader's code, so the code is rebuilt from it for
 * audio.heVoice, with the dictionary form, so qamets and shewa come out as in the Reader.
 */
const STEMS = { Qal: "q", Niphal: "N", Piel: "p", Pual: "P", Hiphil: "h", Hophal: "H", Hithpael: "t" };
export function todayVoice(v, w) {
  if (v.lang !== "he") return w.t;
  const p = String(w.parse || "");
  const parts = p.split(" + ");
  const main = parts.findIndex((x) => !/^(Conjunction|Preposition|Definite article)/.test(x));
  const prefix = parts.slice(0, main < 0 ? 0 : main).map((x) => (/^Definite article/.test(x) ? "Td" : /^Preposition/.test(x) ? "R" : "C"));
  const m = p.match(/Verb: (\w+)[^+]*?(sequential perfect|consecutive perfect|perfect|sequential imperfect|consecutive imperfect|imperfect|jussive|cohortative|imperative|infinitive construct|infinitive absolute|participle)/);
  const form = m ? { "sequential perfect": "q", "consecutive perfect": "q", perfect: "p", "sequential imperfect": "w", "consecutive imperfect": "w", imperfect: "i", jussive: "j", cohortative: "h", imperative: "v", "infinitive construct": "c", "infinitive absolute": "a", participle: "r" }[m[2]] : "";
  const who = (parts.find((x) => /^Verb:/.test(x)) || "").match(/\b(first|second|third)\b/); // the verb's own person, not a suffix's
  const person = m && who ? { first: "1", second: "2", third: "3" }[who[1]] : "";
  const gnm = (parts.find((x) => /^Verb:/.test(x)) || "").match(/\b(singular|plural|dual)\b[ ,]*(masculine|feminine|either gender)?/);
  const gn = person && gnm ? ({ masculine: "m", feminine: "f", "either gender": "c" }[gnm[2]] || "") + gnm[1][0] : "";
  const word = m ? `V${STEMS[m[1]] || "x"}${form}${person}${gn}` : "N";
  const code = "H" + [...prefix, word, /directional/.test(p) ? "Sd" : "", parts.some((x) => /^Suffix/.test(x)) ? "Sp" : ""].filter(Boolean).join("/");
  return heVoice(["", "", "", "", code, w.p || ""], w.t, String(w.p || "").endsWith("\u05be"), w.lemma || undefined);
}

/** Day number of a date (its local calendar day). */
export const dayNumber = (date = new Date()) => Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 864e5);

/**
 * A shuffle of 0…n-1 that needs no list: a small Feistel network is a one-to-one map on 0…2^k-1, and values ≥ n are
 * mapped again until they fall inside ("cycle walking"). So day d and day d+1 land far apart, and no verse comes
 * back until every verse in the pool has had its day (about 13 years for the Greek, 26 for the Hebrew).
 */
function shuffleIndex(i, n, lang) {
  let bits = 2;
  while ((1 << bits) < n) bits++;
  if (bits % 2) bits++;
  const half = bits / 2, mask = (1 << half) - 1;
  const salt = lang === "he" ? 0x9e3779b9 : 0x85ebca6b;
  const round = (r, x) => {
    let h = (Math.imul(x + 1, 0x45d9f3b) ^ Math.imul(r + 1, salt)) >>> 0;
    h = Math.imul(h ^ (h >>> 16), 0x45d9f3b) >>> 0;
    return (h ^ (h >>> 13)) & mask;
  };
  let x = i;
  do {
    let l = x >>> half, r = x & mask;
    for (let k = 0; k < 6; k++) { const t = r; r = l ^ round(k, r); l = t; }
    x = (l << half) | r;
  } while (x >= n);
  return x;
}

/** The pool as [[book, chapter, verse], …] for one language, in Bible order. */
export function poolRefs(pool, lang, bookOrder) {
  const part = (pool && pool[lang]) || {};
  const ids = bookOrder ? bookOrder.filter((id) => part[id]) : Object.keys(part);
  const out = [];
  ids.forEach((id) => String(part[id]).split(" ").forEach((r) => {
    const [c, v] = r.split(".").map(Number);
    if (c && v) out.push([id, c, v]);
  }));
  return out;
}

/** The verse for a day: [book, chapter, verse]. */
export function pickRef(refs, lang, day) {
  const n = refs.length;
  return n ? refs[shuffleIndex(((day % n) + n) % n, n, lang)] : null;
}

const isNoun = (lang, code) => (lang === "grc" ? /^N-/.test(code) && !/-(P|L|G|LG|PG)$/.test(code) : /^[HA]Nc/.test(code));
const isVerb = (lang, code) => (lang === "grc" ? /^V-/.test(code) : /^[HA]V/.test(code));

/**
 * Build Today's verse object ({id, lang, ref, english, words, focus, spoken}) from the Reader's data for one verse.
 * words: the verse's word arrays (data/gnt|hot), lex: the book's lexicon, morph: grammar descriptions by code,
 * english: the BSB verse text, name: the book's name.
 */
export function buildVerse({ lang, bookId, ch, v, name, words, lex, morph, english }) {
  const he = lang === "he";
  const items = words.map((w) => {
    if (he) {
      const parts = heParts(w);
      // as data/votd.json words were built: each part's grammar, a prefix or ending with its own dictionary form
      const parse = parts.map((p) => {
        const d = (morph[p.code] || [p.code])[0];
        if (p.main) return d;
        const e = lex[p.key] || [];
        const g = hePartGloss(p.key, e[2]);
        return `${d} ${heLemma(e[0] || "")}${g ? ` “${g}”` : ""}`.trim();
      }).join(" + ");
      const k = heMainKey(w);
      const e = lex[k] || [];
      const text = heText(w);
      const joined = heJoined(w[5]);
      return { t: text, p: joined ? "־" : heAfter(w[5]), lemma: heLemma(e[0] || ""), gloss: String(e[2] || "").split(": ").pop(),
        parse, en: w[2], k, say: heVoice(w, text, joined, lex) + (joined ? "־" : ""), code: w[4] };
    }
    let keys = String(w[3] || "").split("+").filter(Boolean);
    let codes = String(w[4] || "").split("+");
    // a joined word's parts in the order they are written: κἀγώ = καί + ἐγώ (the source lists ἐγώ first)
    const first = (s) => String(s || "").normalize("NFD").replace(/[^α-ω]/gi, "").toLowerCase().charAt(0);
    if (keys.length === 2 && first((lex[keys[1]] || [])[0]) === first(w[0]) && first((lex[keys[0]] || [])[0]) !== first(w[0])) {
      keys = [keys[1], keys[0]];
      codes = [codes[1], codes[0]];
    }
    const e = lex[keys[0]] || [];
    const item = { t: w[0], p: String(w[5] || "").replace(/[¶¬]/g, ""), pre: w[6] || "", lemma: e[0] || "",
      gloss: String(e[2] || "").split(": ").pop(), parse: codes.map((c) => (morph[c] || [c])[0]).join(" + "), en: w[2], k: keys[0] || "", say: w[0], code: w[4] };
    if (keys.length > 1) item.parts = keys.map((key) => [(lex[key] || [])[0] || "", String((lex[key] || [])[2] || "").split(": ").pop(), key]);
    return item;
  });
  // the word shown first: the verse's first ordinary noun, else its first verb, else its first word
  const mainCode = (w) => (he ? (heParts(w).find((p) => p.main) || {}).code || "" : String(w[4] || "").split("+")[0]);
  let focus = words.findIndex((w) => isNoun(lang, mainCode(w)));
  if (focus < 0) focus = words.findIndex((w) => isVerb(lang, mainCode(w)));
  return {
    id: `${bookId}-${ch}-${v}`, lang, ref: `${bookId === "PSA" ? "Psalm" : name} ${ch}:${v}`,
    english: String(english || "").replace(/\u0001\d+\u0001/g, "").trim(),
    words: items, focus: Math.max(0, focus),
    spoken: verseSpeech(words, lang, lex), // what "Listen to the verse" says: the Reader's own verse text
  };
}
