// The Dictionary (Words tab): search both lexicons, open a full entry with every place a word appears.
// Data: data/lex/<greek|hebrew>-index.json for search; data/lex/<G|H>/<nn>.json for entries, built by
// tools/build_data.py + tools/build_dictionary.py (entry = [lemma, translit, morph, gloss, def, rel, occ, forms]).
import * as store from "./store.js";
import * as data from "./data.js";
import * as nav from "./nav.js";
import { strongs, shortGrammar, englishHTML } from "./reader.js";
import { heText, heAfter, heJoined, heEnglish, heTranslit, heShortGrammar } from "./hebrew.js";
import { head } from "./screens.js";
import { sayButton } from "./audio.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const LANGS = { G: { name: "greek", lang: "grc", dir: "ltr", where: "New Testament", label: "Greek" },
                H: { name: "hebrew", lang: "he", dir: "rtl", where: "Old Testament", label: "Hebrew" } };
/** STEPBible glosses can be "general: specific" ("to love: lover", "to hear: hear"); show both when they differ. */
function glossText(gloss) {
  const [general, specific] = String(gloss || "").split(": ");
  if (!specific) return general;
  const g = general.toLowerCase().replace(/^to /, "");
  const s = specific.toLowerCase().replace(/^to /, "");
  return g === s || g.includes(s) ? general : `${general} (${specific})`;
}
const compact = glossText;
const plain = (s) => String(s || "").replace(/^\//, "").replace(/\//g, "");

// ---------------------------------------------------------------- text matching

const greekNorm = (s) => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
  .replace(/ς/g, "σ").replace(/[^α-ω]/g, "");
const FINALS = { "ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ" };
const hebrewNorm = (s) => String(s).replace(/[\u0591-\u05c7]/g, "").replace(/[ךםןףץ]/g, (c) => FINALS[c])
  .replace(/[^א-ת]/g, "");
/** Looser spelling for pronunciations: y/u, ph/f, w/v, ch/kh/h, tz/ts and doubled letters count as the same
 *  (kyrios = kurios, huios = uhios, nefesh = ne.phesh, chesed = hesed, erets = 'A.retz).
 *  Must match loose_norm() in tools/build_dictionary.py. */
const looseNorm = (s) => latinNorm(s).replace(/ph/g, "f").replace(/[ck]h/g, "h").replace(/tz/g, "ts").replace(/y/g, "u")
  .replace(/w/g, "v").replace(/h/g, "").replace(/(.)\1+/g, "$1");
/** Consonants only, for spellings that differ in their vowels (bereishit, b'reshit, vayomer = be.re.Shit, vai.Yo.mer). */
const skeleton = (loose) => loose.replace(/[aeiou]/g, "");
/** Letters to change, add or remove to turn one spelling into another (short strings only). */
function distance(a, b) {
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[b.length];
}
const latinNorm = (s) => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]/g, "");
const IS_GREEK = /[\u0370-\u03ff\u1f00-\u1fff]/;
const IS_HEBREW = /[\u0590-\u05ff]/;

const prepared = {};
/** The search list for one language ("G" or "H"), with normalised fields. */
function index(letter) {
  if (!prepared[letter]) {
    prepared[letter] = data.getJSON(`data/lex/${LANGS[letter].name}-index.json`).then((list) => list.map((e) => {
      const [key, lemma = "", translit = "", gloss = "", count = 0, kw = ""] = e;
      return {
        key, lemma: plain(lemma) || translit || key, translit, gloss, count, letter, // a few entries have no headword (G2199H)
        num: parseInt(key.slice(1), 10),
        lemmaN: letter === "G" ? greekNorm(lemma) : hebrewNorm(lemma),
        trN: latinNorm(translit),
        trL: looseNorm(translit),
        main: String(gloss).split(": ")[0].toLowerCase().trim(),
        alt: (String(gloss).split(": ")[1] || "").toLowerCase().trim(),
        slash: String(gloss).toLowerCase().split(/[:/]\s*/).map((x) => x.trim()), // "in/on/among" → in, on, among
        words: ` ${String(gloss).toLowerCase().replace(/[^a-z0-9']+/g, " ").trim()} `,
        tg: ` ${String(kw).split("|")[0]} `, // English used for it in the verses
        kw: ` ${String(kw).split("|").pop()} `, // English words from the definition (lower ranked)
      };
    }));
    prepared[letter].catch(() => { delete prepared[letter]; }); // try again next time (e.g. back online)
  }
  return prepared[letter];
}

/** Score an entry against a query; lower is better, null = no match. */
function scorer(q) {
  const raw = q.trim();
  const strong = raw.match(/^([GHgh])?\s*0*(\d{1,5})([A-Za-z])?$/);
  if (strong) {
    const letter = strong[1] ? strong[1].toUpperCase() : "";
    const n = Number(strong[2]);
    const sense = strong[3] ? strong[3].toUpperCase() : "";
    return (e) => (e.num === n && (!letter || e.letter === letter) && (!sense || e.key.slice(-1) === sense) ? (e.key.length === 5 ? 0 : 1) : null);
  }
  if (IS_GREEK.test(raw) || IS_HEBREW.test(raw)) {
    const greek = IS_GREEK.test(raw);
    const qn = greek ? greekNorm(raw) : hebrewNorm(raw);
    if (!qn) return () => null;
    return (e) => {
      if ((e.letter === "G") !== greek) return null;
      if (e.lemmaN === qn) return 0;
      if (e.lemmaN.startsWith(qn)) return 1;
      return qn.length > 1 && e.lemmaN.includes(qn) ? 3 : null;
    };
  }
  const qw = raw.toLowerCase().replace(/[^a-z0-9' ]+/g, " ").replace(/\s+/g, " ").trim();
  const qn = latinNorm(raw);
  const ql = looseNorm(raw);
  const many = qw.split(" ").filter((x) => x.length > 2);
  if (!qn) return () => null;
  return (e) => {
    if (e.main === qw || e.main === `to ${qw}` || e.alt === qw || e.alt === `to ${qw}`) return 0.2;
    if (e.slash.includes(qw) || e.slash.includes(`to ${qw}`)) return 0.3;
    if (e.trN === qn) return 0.4;
    if (ql.length >= 3 && e.trL === ql) return 0.6;
    if (e.words.includes(` ${qw} `)) return 1;
    if (qw.length >= 3 && e.tg.includes(` ${qw} `)) return 1.2;
    if (qn.length >= 3 && e.trN.startsWith(qn)) return 1.5;
    if (ql.length >= 5 && e.trL.startsWith(ql)) return 1.7;
    if (qw.length >= 3 && e.words.includes(` ${qw}`)) return 2;
    if (qw.length >= 3 && e.kw.includes(` ${qw} `)) return 2.5;
    if (qn.length >= 4 && e.trN.includes(qn)) return 3;
    if (qw.length >= 4 && e.kw.includes(` ${qw}`)) return 3.5;
    if (many.length > 1 && many.every((x) => e.words.includes(` ${x}`) || e.tg.includes(` ${x}`) || e.kw.includes(` ${x}`))) return 3.8; // "holy spirit"
    return null;
  };
}

const formLists = {};
/** Written forms in the text that differ from their dictionary form (loaded only when Greek or Hebrew is typed). */
function formsList(letter) {
  if (!formLists[letter]) {
    formLists[letter] = data.getJSON(`data/lex/${LANGS[letter].name}-forms.json`).catch(() => {
      delete formLists[letter];
      return {};
    });
  }
  return formLists[letter];
}

const soundLists = {};
const soundsLoaded = {};
/** Pronunciations of written words (be.re.Shit → bereshit), loaded in the background on the first English-letter search. */
function soundsList(letter) {
  if (!soundLists[letter]) {
    soundLists[letter] = data.getJSON(`data/lex/${LANGS[letter].name}-sounds.json`).then((map) => {
      const skel = new Map(); // consonants → [pronunciation, …]
      for (const sound of Object.keys(map)) {
        const k = skeleton(sound);
        if (k.length < 3) continue;
        const list = skel.get(k) || [];
        list.push(sound);
        skel.set(k, list);
      }
      soundsLoaded[letter] = { map, skel };
      return soundsLoaded[letter];
    }).catch(() => { delete soundLists[letter]; return null; });
  }
  return soundLists[letter];
}

/** Matching entries, best first. A word typed exactly as written in a verse (ἠγάπησεν, bereshit) finds its entry.
 *  Returns { hits, pending }: pending resolves when the pronunciation lists arrive, so results can be redrawn. */
async function search(q, which) {
  const letters = which === "both" ? ["G", "H"] : [which];
  const lists = await Promise.all(letters.map(index));
  const score = scorer(q);
  const best = new Map(); // key → [score, entry, found as a written form]
  for (const list of lists) {
    for (const e of list) {
      const s = score(e);
      if (s != null) best.set(e.key, [s + (e.count ? 0 : 5), e, false]); // words not in the Bible text (lexicon only) go last
    }
  }
  const raw = q.trim();
  const letter = IS_GREEK.test(raw) ? "G" : IS_HEBREW.test(raw) ? "H" : "";
  if (letter && letters.includes(letter)) {
    const norm = letter === "G" ? greekNorm(raw) : hebrewNorm(raw);
    const keys = (await formsList(letter))[norm] || [];
    for (const [i, k] of keys.entries()) {
      const e = await resolveKey(k);
      if (e && !(best.has(e.key) && best.get(e.key)[0] <= 0)) best.set(e.key, [0.05 + i / 100, e, true]);
    }
  }
  // Pronunciations of written words, prefixes and all: "bereshit" → רֵאשִׁית; consonants alone catch other spellings
  let pending = null;
  const ql = looseNorm(raw);
  const isStrong = /^[GHgh]?\s*\d/.test(raw);
  if (!letter && !isStrong && ql.length >= 4) {
    const waiting = [];
    for (const L of letters) {
      const sounds = soundsLoaded[L];
      if (!sounds) { waiting.push(soundsList(L)); continue; }
      const add = async (keys, score, how) => {
        for (const [i, k] of keys.entries()) {
          const e = await resolveKey(k);
          if (e && !(best.has(e.key) && best.get(e.key)[0] <= score)) best.set(e.key, [score + i / 1000, e, how]);
        }
      };
      const words = raw.split(/\s+/).map(looseNorm).filter((w) => w.length >= 3);
      if (words.length > 1) {
        // a phrase ("shema yisrael", "bara elohim"): each word as written, or as its dictionary form
        // results follow the order of the words typed ("bereshit bara elohim" → רֵאשִׁית, בָּרָא, אֱלֹהִים)
        for (const [i, w] of words.entries()) await add(sounds.map[w] || [], 0.8 + i / 10, true);
        for (const e of await index(L)) {
          const i = e.count ? words.indexOf(e.trL) : -1;
          if (i >= 0 && !(best.has(e.key) && best.get(e.key)[0] <= 0.8 + i / 10)) best.set(e.key, [0.8 + i / 10, e, false]);
        }
        continue;
      }
      await add(sounds.map[ql] || [], 0.7, true);
      // Same consonants, nearly the same spelling (bereishit, b'reshit → be.re.Shit): closest first, at most two letters out
      const near = (sounds.skel.get(skeleton(ql)) || [])
        .map((snd) => [distance(ql, snd), snd]).filter(([d, snd]) => d > 0 && d <= Math.min(2, Math.floor(ql.length / 3)) && snd !== ql)
        .sort((a, b) => a[0] - b[0]).slice(0, 4);
      for (const [d, snd] of near) await add(sounds.map[snd] || [], 1.6 + d / 10, "similar");
    }
    if (waiting.length) pending = Promise.all(waiting);
  }
  const hits = [...best.values()].sort((a, b) => a[0] - b[0] || b[1].count - a[1].count).map(([, e, form]) => ({ e, form }));
  return { hits, pending };
}

/** Dictionary entries that a Greek word as written may belong to (the Septuagint isn't tagged word by word yet):
 *  written forms known from the New Testament, then dictionary forms, then words that start the same. */
const lemmaMaps = {};

/** Spellings to try for a Septuagint word: Swete's spellings (ει for ι, unassimilated συν-/ἐν-) and the word
 * without its past-tense augment (ἐκληρονόμησαν → κληρονομ…, ἐπεμαρτύρατο → ἐπιμαρτυρ…). Works on greekNorm text. */
function lxxVariants(norm) {
  const out = new Set([norm]);
  const add = (x) => { if (x && x.length >= 3) out.add(x); };
  add(norm.replace(/ει/g, "ι"));
  const nasal = (x) => x.replace(/^(συν|εν)(?=[κγχξ])/, (m) => m.slice(0, -1) + "γ")
    .replace(/^(συν|εν)(?=[πβφψμ])/, (m) => m.slice(0, -1) + "μ")
    .replace(/^(συν|εν)(?=λ)/, (m) => m.slice(0, -1) + "λ").replace(/^συν(?=σ)/, "συ");
  [...out].forEach((x) => add(nasal(x)));
  const PREP = [["απε", "απο"], ["αφε", "αφι"], ["επε", "επι"], ["εφε", "εφι"], ["κατε", "κατα"], ["καθε", "καθι"],
    ["μετε", "μετα"], ["παρε", "παρα"], ["διε", "δια"], ["ανε", "ανα"], ["υπε", "υπο"], ["προσε", "προσ"],
    ["περιε", "περι"], ["συνε", "συν"], ["ενε", "εν"], ["εξε", "εκ"], ["εισε", "εισ"]];
  [...out].forEach((x) => {
    for (const [a, b] of PREP) if (x.startsWith(a) && x.length > a.length + 2) add(b + x.slice(a.length));
    if (/^ε[^ιυ]/.test(x)) add(x.slice(1)); // ἔπταισεν → πταισεν (not ει-, ευ- which are often the word itself)
    if (/^η/.test(x)) { add("ε" + x.slice(1)); add("α" + x.slice(1)); } // ἠρήμωται → ερημ…, ἤκουσαν → ακου…
    if (/^ω/.test(x)) add("ο" + x.slice(1));
  });
  return [...out];
}

/** Dictionary entries for a written Greek word that isn't tagged (the Septuagint): its form in the New Testament,
 * a headword spelt the same, else headwords sharing the longest start with one of its spellings (marked as guesses). */
export async function lookupForm(word) {
  const norm = greekNorm(word);
  if (!norm) return [];
  const found = new Map();
  const forms = await formsList("G");
  const list = await index("G");
  const variants = lxxVariants(norm);
  for (const v of variants) {
    for (const k of forms[v] || []) {
      const e = await resolveKey(k);
      if (e) found.set(e.key, e);
    }
    list.filter((e) => e.lemmaN === v).forEach((e) => found.set(e.key, e));
    if (found.size) break; // the plain spelling first; variants only when it finds nothing
  }
  if (!found.size && norm.length >= 4) {
    // no exact match: (1) a stem of the word plus a usual dictionary ending (μισοῦντας → μισ+έω, κοιμηθῆναι →
    // κοιμ+άω, στενάξουσιν → στενα(ξ→ζ)+ω); (2) headwords sharing the longest start. Names only for capitalised words.
    const isName = word.trim().charAt(0) !== word.trim().charAt(0).toLowerCase();
    const ok = (e) => e.count && (isName || e.lemma.charAt(0) === e.lemma.charAt(0).toLowerCase());
    if (!lemmaMaps.G) {
      lemmaMaps.G = new Map();
      list.forEach((e) => { if (!lemmaMaps.G.has(e.lemmaN)) lemmaMaps.G.set(e.lemmaN, []); lemmaMaps.G.get(e.lemmaN).push(e); });
    }
    const byLemma = lemmaMaps.G;
    const ENDINGS = ["ω", "εω", "αω", "οω", "ευω", "ιζω", "αζω", "ζω", "ομαι", "οσ", "ον", "η", "α", "ισ", "ησ", "υσ", "μι"];
    const SHORT = ["εω", "αω", "οω"]; // a 3-letter stem only for contract verbs (μισ-έω, βο-άω)
    const SWAP = { ξ: ["γ", "κ", "χ", "ζ", "σσ"], ψ: ["π", "β", "φ", "πτ"], σ: ["", "ζ", "δ", "θ", "τ"], θ: ["", "ζ"] };
    let stemHits = [];
    let stemLen = 0;
    for (const v of variants) {
      for (let k = v.length - 1; k >= (isName ? 4 : 3) && k > stemLen; k--) {
        const stem = v.slice(0, k);
        const last = stem.slice(-1);
        const stems = [stem].concat((SWAP[last] || []).map((x) => stem.slice(0, -1) + x));
        const hits = [];
        stems.forEach((st) => (k === 3 ? SHORT : ENDINGS).forEach((end) => (byLemma.get(st + end) || [])
          .forEach((e) => { if (ok(e) && (!isName || e.lemma.charAt(0) !== e.lemma.charAt(0).toLowerCase())) hits.push(e); })));
        if (hits.length) { stemHits = hits; stemLen = k; break; }
      }
    }
    let best = [];
    let bestLen = 0;
    for (const v of variants) {
      for (let k = v.length - 1; k >= Math.max(4, v.length - 4) && k >= bestLen; k--) {
        const stem = v.slice(0, k);
        const hits = list.filter((e) => ok(e) && e.lemmaN.startsWith(stem)
          && (!isName || e.lemma.charAt(0) !== e.lemma.charAt(0).toLowerCase())); // a name only matches a name
        if (hits.length) {
          if (k > bestLen) { best = hits; bestLen = k; }
          break;
        }
      }
    }
    if (stemHits.length && (stemLen >= bestLen || (stemLen >= 4 && stemLen === bestLen - 1))) best = stemHits;
    best.sort((a, c) => c.count - a.count).slice(0, 4).forEach((e) => found.set(e.key, { ...e, guess: true }));
  }
  return [...found.values()].sort((a, c) => (a.guess ? 1 : 0) - (c.guess ? 1 : 0) || c.count - a.count).slice(0, 6);
}

/** Open the Words tab with a search already typed (e.g. "Search the dictionary for …" from the Septuagint). */
export function setQuery(q) { lastQuery = String(q || ""); }

export { rowHTML as entryRowHTML };

const keyMaps = {};
/** The lexicon key an outside key belongs to: exact, else the bare number, else its most common lettered sense. */
export async function resolveKey(key) {
  const letter = String(key).charAt(0).toUpperCase();
  if (!LANGS[letter]) return null;
  if (!keyMaps[letter]) {
    keyMaps[letter] = index(letter).then((list) => new Map(list.map((e) => [e.key, e])));
    keyMaps[letter].catch(() => { delete keyMaps[letter]; }); // try again next time (e.g. back online)
  }
  const byKey = await keyMaps[letter];
  if (byKey.has(key)) return byKey.get(key);
  const num = String(key).replace(/^([GH])0*(\d+).*$/i, (m, l, n) => l.toUpperCase() + n.padStart(4, "0"));
  if (byKey.has(num)) return byKey.get(num);
  // a bare number with lettered senses only (H7462A…D): the most common sense, not the first letter
  let best = null;
  for (const c of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
    const e = byKey.get(num + c);
    if (e && (!best || (e.count || 0) > (best.count || 0))) best = e;
  }
  return best;
}

// ---------------------------------------------------------------- shared bits

const lemmaHTML = (e, cls = "dict-lemma") =>
  `<span class="${cls}" lang="${LANGS[e.letter].lang}" dir="${LANGS[e.letter].dir}">${esc(e.lemma)}</span>`;
const timesText = (n, where) => (n === 1 ? `Once in the ${where}` : `${n.toLocaleString("en-GB")} times in the ${where}`);
const showStrongs = (key) => (/^H90\d\d/.test(key) ? "" : strongs(key));

const notInText = (e) => (/^H90\d\d/.test(e.key) ? "joined to words" : e.letter === "G" ? "not in the NT" : "not in this text");

function rowHTML(e, asForm = false) {
  const tr = e.letter === "H" ? heTranslit(e.translit) : e.translit;
  const sn = showStrongs(e.key);
  return `<li><a class="row dict-row" href="#/words/${encodeURIComponent(e.key)}">
      ${lemmaHTML(e)}
      <span class="row-main"><span class="row-title">${esc(compact(e.gloss) || "—")}</span>
        <span class="row-sub">${asForm ? `<span class="dict-form">${asForm === "similar" ? "Sounds like a word in the text" : "Dictionary form of your word"}</span> · ` : ""}${esc(tr)}${tr && sn ? " · " : ""}${esc(sn)}</span></span>
      <span class="row-end">${e.count ? `${e.count.toLocaleString("en-GB")}<span class="sr"> times</span>×` : `<span class="dict-none">${notInText(e)}</span>`}</span>
    </a></li>`;
}

const RECENT_MAX = 12;
function addRecent(key) {
  const list = (store.get("recentWords") || []).filter((k) => k !== key);
  list.unshift(key);
  store.set("recentWords", list.slice(0, RECENT_MAX));
}

// ---------------------------------------------------------------- search screen

let lastQuery = "";
let lastScroll = 0;

const COMMON = {
  G: { n: 25, note: "The 25 most common words make up about half of the Greek New Testament (48%), and 319 words appear 50 times or more." },
  H: { n: 25, note: "The 100 most common words make up nearly half of the Hebrew Old Testament (47%), not counting the little words joined to the front, such as “and” and “the”." },
};

async function renderSearch(main) {
  const which = store.get("dictLang");
  const tab = (v, label) => `<button type="button" data-lang="${v}" aria-pressed="${v === which}">${label}</button>`;
  main.innerHTML = `<div class="screen dict">
    ${head("Words", "The dictionary: look up any Greek or Hebrew word")}
    <form class="dict-search" role="search">
      <label class="sr" for="dict-q">Search the dictionary</label>
      <input id="dict-q" type="search" placeholder="English, Greek, Hebrew or Strong's" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="search" value="${esc(lastQuery)}">
    </form>
    <p class="field-help dict-help">Try “word”, λόγος, logos, דָּבָר, bereshit, G3056 or H1697.</p>
    <div class="switch dict-switch" role="group" aria-label="Language">${tab("both", "Both")}${tab("G", "Greek")}${tab("H", "Hebrew")}</div>
    <p class="sr" role="status" aria-live="polite" data-status></p>
    <div class="dict-results"></div>
  </div>`;
  document.title = "Words · Aleph to Omega";
  const input = main.querySelector("#dict-q");
  const out = main.querySelector(".dict-results");
  const status = main.querySelector("[data-status]");
  const announce = (text) => { if (status.textContent !== text) status.textContent = text; };
  let shown = 60;
  let run = 0;

  const draw = async () => {
    const id = ++run;
    const q = input.value;
    lastQuery = q;
    const lang = store.get("dictLang");
    if (!q.trim()) {
      out.innerHTML = `<p class="muted">Loading…</p>`;
      const recent = store.get("recentWords") || [];
      const letters = lang === "both" ? ["G", "H"] : [lang];
      let html = "";
      try {
        if (recent.length) {
          const found = (await Promise.all(recent.map(resolveKey))).filter(Boolean)
            .filter((e) => lang === "both" || e.letter === lang);
          if (found.length) {
            html += `<div class="dict-section"><h2>Recently looked up</h2><ul class="rows">${found.map((x) => rowHTML(x)).join("")}</ul>
              <p><button type="button" class="link-btn" data-clear>Clear this list</button></p></div>`;
          }
        }
        for (const L of letters) {
          const list = (await index(L)).filter((e) => e.count).sort((a, b) => b.count - a.count).slice(0, 100);
          html += `<div class="dict-section"><h2>Most common in the ${LANGS[L].label === "Greek" ? "Greek New Testament" : "Hebrew Old Testament"}</h2>
            <p class="muted">${COMMON[L].note}</p>
            <ol class="rows dict-common" data-letter="${L}">${list.slice(0, COMMON[L].n).map((x) => rowHTML(x)).join("")}</ol>
            <p><button type="button" class="btn secondary" data-more-common="${L}">Show the top 100</button></p></div>`;
        }
      } catch {
        html = `<div class="note"><p>The dictionary couldn't load. Connect to the internet once and it will be saved for offline use.</p></div>`;
      }
      if (id !== run) return;
      out.innerHTML = html;
      out.querySelectorAll("[data-more-common]").forEach((b) => b.addEventListener("click", async () => {
        const L = b.dataset.moreCommon;
        const list = (await index(L)).filter((e) => e.count).sort((a, c) => c.count - a.count).slice(0, 100);
        out.querySelector(`.dict-common[data-letter="${L}"]`).innerHTML = list.map((x) => rowHTML(x)).join("");
        b.remove();
      }));
      out.querySelector("[data-clear]")?.addEventListener("click", () => { store.set("recentWords", []); draw(); });
      return;
    }
    let hits;
    try {
      const found = await search(q, lang);
      hits = found.hits;
      // The pronunciation lists load in the background the first time; search again when they arrive
      if (found.pending) found.pending.then(() => { if (input.value === q) draw(); });
    } catch {
      if (id === run) out.innerHTML = `<div class="note"><p>The dictionary couldn't load. Connect to the internet once and it will be saved for offline use.</p></div>`;
      return;
    }
    if (id !== run) return;
    announce(!hits.length ? "No matches" : hits.length === 1 ? "1 match" : `${hits.length} matches`);
    if (!hits.length) {
      out.innerHTML = `<p class="dict-count">No matches for “${esc(q.trim())}”.</p>
        <p class="muted">Search for an English meaning (shepherd), a Greek or Hebrew word with or without accents and vowels, its pronunciation (poimen, roeh) or a Strong's number (G4166, H7462).</p>`;
      return;
    }
    out.innerHTML = `<p class="dict-count">${hits.length === 1 ? "1 match" : `${hits.length.toLocaleString("en-GB")} matches`}</p>
      <ul class="rows">${hits.slice(0, shown).map((h) => rowHTML(h.e, h.form)).join("")}</ul>
      ${hits.length > shown ? `<p><button type="button" class="btn secondary" data-more>Show more</button></p>` : ""}`;
    out.querySelector("[data-more]")?.addEventListener("click", () => { shown += 60; draw(); });
  };

  let timer = 0;
  input.addEventListener("input", () => { shown = 60; clearTimeout(timer); timer = setTimeout(draw, 120); });
  main.querySelector("form").addEventListener("submit", (e) => { e.preventDefault(); input.blur(); draw(); });
  main.querySelectorAll("[data-lang]").forEach((b) => b.addEventListener("click", () => {
    store.set("dictLang", b.dataset.lang);
    main.querySelectorAll("[data-lang]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    shown = 60;
    draw();
  }));
  out.addEventListener("click", (e) => {
    if (e.target.closest("a.dict-row")) { lastScroll = window.scrollY; nav.remember("#/words", true); }
  });
  await draw();
  window.scrollTo(0, nav.recall("#/words") ? lastScroll : 0);
}

// ---------------------------------------------------------------- definitions

// New Testament references in Abbott-Smith ("Mat.8.8") → Reader book ids. Its Old Testament references follow the
// Septuagint's numbering, so they are left as plain text.
const BOOK_BY_STEP = Object.fromEntries(("Mat MAT Mrk MRK Luk LUK Jhn JHN Act ACT Rom ROM 1Co 1CO 2Co 2CO Gal GAL Eph EPH Php PHP " +
  "Col COL 1Th 1TH 2Th 2TH 1Ti 1TI 2Ti 2TI Tit TIT Phm PHM Heb HEB Jas JAS 1Pe 1PE 2Pe 2PE 1Jn 1JN 2Jn 2JN 3Jn 3JN Jud JUD Jude JUD " +
  "Rev REV").split(" ").reduce((pairs, x, i, all) => (i % 2 ? pairs : pairs.concat([[x, all[i + 1]]])), []));

const NT_CHAPTERS = { MAT: 28, MRK: 16, LUK: 24, JHN: 21, ACT: 28, ROM: 16, "1CO": 16, "2CO": 13, GAL: 6, EPH: 6, PHP: 4, COL: 4,
  "1TH": 5, "2TH": 3, "1TI": 6, "2TI": 4, TIT: 3, PHM: 1, HEB: 13, JAS: 5, "1PE": 5, "2PE": 3, "1JN": 5, "2JN": 1, "3JN": 1, JUD: 1, REV: 22 };

/** Turn a lexicon definition (STEPBible markup) into safe HTML: bold, italics, line breaks, linked NT references. */
export function definitionHTML(raw) {
  const parts = [];
  const re = /<\s*(\/?)\s*([A-Za-z]+)([^>]*)>/g;
  let last = 0;
  let m;
  // long "a/b/c" lists may break after a slash
  const text = (t) => esc(t.replace(/&gt;/g, ">").replace(/&lt;/g, "<").replace(/&amp;/g, "&")).replace(/\//g, "/<wbr>");
  while ((m = re.exec(raw))) {
    parts.push(text(raw.slice(last, m.index)));
    last = re.lastIndex;
    const [, close, name, attrs] = m;
    const tag = name.toLowerCase();
    if (tag === "b") parts.push(close ? "</strong>" : "<strong>");
    else if (tag === "i") parts.push(close ? "</em>" : "<em>");
    else if (tag === "br" || tag === "lb") parts.push("\n");
    else if (tag === "ref") {
      if (close) { parts.push("</ref>"); continue; }
      const r = (attrs.match(/='([^']*)'/) || [])[1] || "";
      const rm = r.match(/^(\w+)\.(\d+)\.(\d+)/);
      const id = rm && BOOK_BY_STEP[rm[1]];
      const real = id && Number(rm[2]) >= 1 && Number(rm[2]) <= NT_CHAPTERS[id]; // a few source typos, e.g. "Mat.92.6"
      parts.push(real ? `<ref href="#/read/${id}/${rm[2]}/${rm[3]}">` : "<ref>");
    }
    // other source tags (note, greek, corr, author, date, re, def, a) are dropped; their text stays
  }
  parts.push(text(raw.slice(last)));
  let html = parts.join("")
    .replace(/<ref href="([^"]*)">([\s\S]*?)<\/ref>/g, '<a href="$1">$2</a>')
    .replace(/<ref>([\s\S]*?)<\/ref>/g, "$1")
    .replace(/<\/?ref[^>]*>/g, "")
    // Mentions of other entries ("H0157H", "G2424") open that entry (only in text, never inside a tag)
    .replace(/(^|>)([^<]*)/g, (m, gt, txt) => gt + txt.replace(/\b([GH]\d{4,5}[A-Z]?)\b/g, '<a href="#/words/$1">$1</a>'));
  // One line per sense: "__1." (Abbott-Smith) and "1a)" (Hebrew outline) start indented lines.
  // A few entries run a marker on mid-line (no break in the source): start a new line there too.
  html = html.replace(/\s*__(?=\s*\S)/g, "\n__");
  const lines = html.split("\n").map((l) => l.trim().replace(/^:\s*/, "")).filter(Boolean); // some entries start with ": …"
  return lines.map((line) => {
    let depth = 0;
    let body = line;
    // Abbott-Smith: __I. (main division), __1. (sense), __(a) / __(1) / __(α) (sub-sense)
    const as = body.match(/^__\s*([IVX]+\.|\d+\.?|\([a-z]{1,3}\)|\(\d\)|\([α-ω]\)|[α-ω]\.?)(?=\s|$)\s*/);
    // Hebrew outline: 1) 1a) 1a1)
    const he = body.match(/^(\d+(?:[a-z]\d*)*[a-z]?)\)\s*/);
    if (as) {
      depth = /^[IVX]/.test(as[1]) ? 0 : /^\d/.test(as[1]) ? 1 : 2;
      body = `<span class="sense">${as[1]}</span> ${body.slice(as[0].length)}`;
    } else if (he) {
      depth = (he[1].match(/\d+|[a-z]/g) || []).length - 1;
      body = `<span class="sense">${he[1]})</span> ${body.slice(he[0].length)}`;
    }
    return `<p class="def-line" style="--depth:${Math.min(depth, 4)}">${body.replace(/^__\s*/, "")}</p>`;
  }).join("");
}

// ---------------------------------------------------------------- parts of speech

const POS = [
  [/^N:N-M-P/, "Name of a man"], [/^N:N-F-P/, "Name of a woman"], [/^N:N--PG/, "Name of a people"],
  [/^N:N-.?-?L|^N:N--L/, "Name of a place"], [/^N:N.*T/, "Title or name"], [/^N:A--LG/, "Name of a people"], [/^N:/, "Name"],
  [/:V\b/, "Verb"], [/:N-M\/F|:N-M-F/, "Noun"], [/:N-M/, "Noun, masculine"], [/:N-F/, "Noun, feminine"], [/:N-N/, "Noun, neuter"],
  [/:N\b/, "Noun"], [/:A-NUI/, "Number"], [/:A/, "Adjective"], [/:ADV|:Adv/, "Adverb"], [/:PREP|:Prep/, "Preposition"],
  [/:CONJ|:Conj/, "Conjunction"], [/:COND|:Cond/, "Conditional word (if)"], [/:PRT-N/, "Negative (not)"], [/:PRT/, "Particle"],
  [/:INJ|:Intj/, "Exclamation"], [/:Intg/, "Question word"], [/:DemP/, "Pointing word (this, that)"], [/:D\b/, "Article (the)"],
  [/:P-\d|:P\b|:PerP/, "Pronoun"], [/:F-\d/, "Pronoun (-self)"], [/:S-\d/, "Pronoun (my, your…)"],
  [/:R\b|:RelP/, "Relative word (who, which)"], [/:I\b/, "Question word"], [/:X\b|:IndP/, "Pronoun (someone, anyone)"],
  [/:Q\b|:K\b/, "Pronoun (such, as many as)"], [/:C-/, "Pronoun (one another)"], [/:T\b/, "Article (the)"],
  [/:Neg/, "Negative (not)"], [/:Part/, "Particle"], [/^Prefix/, "Prefix"],
];
export function partOfSpeech(code, key) {
  if (/^H90\d\d/.test(key)) return "Part of a word (prefix or suffix)";
  const c = String(code || "");
  const found = POS.find(([re]) => re.test(c));
  return found ? found[1] : "";
}

// ---------------------------------------------------------------- an entry

const entryMemory = { key: "", open: new Set(), scroll: 0 };

function verseLine(letter, w, words, wi) {
  // A window of words around the one looked up, so long verses stay short
  const from = Math.max(0, wi - 5);
  const to = Math.min(words.length, wi + 6);
  const bits = [];
  for (let i = from; i < to; i++) {
    const x = words[i];
    let t;
    if (letter === "H") t = esc(heText(x)) + esc(heAfter(x[5]));
    else t = esc(x[6] || "") + esc(x[0]) + esc(String(x[5] || "").replace(/[¶¬]/g, ""));
    if (i === wi) t = `<mark>${t}</mark>`;
    bits.push(t + (letter === "H" && heJoined(x[5]) ? "" : " "));
  }
  return (from > 0 ? "… " : "") + bits.join("").trim() + (to < words.length ? " …" : "");
}

async function renderEntry(main, rawKey) {
  main.innerHTML = `<div class="screen dict-entry"><p class="muted">Loading…</p></div>`;
  let e;
  let failed = false;
  try {
    e = await resolveKey(rawKey);
  } catch { e = null; failed = true; }
  if (!main.querySelector(".dict-entry") || location.hash !== `#/words/${encodeURIComponent(rawKey)}`) return;
  if (!e) {
    main.innerHTML = `<div class="screen dict-entry">
      <p><button type="button" class="back-btn" data-back>‹ Back</button></p>
      <div class="note"><p>${failed ? "The dictionary couldn't load. Connect to the internet once and it will be saved for offline use."
        : "That word isn't in the dictionary."}</p></div></div>`;
    main.querySelector("[data-back]").addEventListener("click", () => nav.goBack("#/words"));
    document.title = "Words · Aleph to Omega";
    return;
  }
  const L = LANGS[e.letter];
  const hash = `#/words/${encodeURIComponent(rawKey)}`;
  let entry;
  let books;
  let morph;
  let all;
  try {
    [entry, books, morph, all] = await Promise.all([
      data.getJSON(`data/lex/${e.letter}/${e.key.slice(1, 3)}.json`).then((c) => c[e.key] || []),
      data.books(), data.morph(e.letter === "G" ? "grc" : "he"), index(e.letter),
    ]);
  } catch {
    main.innerHTML = `<div class="screen dict-entry"><p><button type="button" class="back-btn" data-back>‹ Back</button></p>
      <div class="note"><p>This entry couldn't load. Connect to the internet once and it will be saved for offline use.</p></div></div>`;
    main.querySelector("[data-back]").addEventListener("click", () => nav.goBack("#/words"));
    return;
  }
  if (location.hash !== hash) return; // moved on while loading
  const [, , pos, , def = "", , occ = {}, forms = []] = entry;
  addRecent(e.key);
  document.title = `${e.lemma} · Words · Aleph to Omega`;

  const tr = e.letter === "H" ? heTranslit(e.translit) : e.translit;
  const sn = showStrongs(e.key);
  const posText = partOfSpeech(pos, e.key);
  const aramaic = /^A:/.test(pos || "");
  const bookList = books.filter((b) => occ[b.id]);
  const total = bookList.reduce((n, b) => n + occ[b.id].split(" ").length, 0);
  const siblings = all.filter((x) => x.num === e.num && x.key !== e.key);
  const grammarLabel = (code) => {
    const d = (morph[code] || [code])[0];
    return e.letter === "H" ? heShortGrammar(d) : shortGrammar(d);
  };
  const formRows = (list) => list.map(([f, n, code]) => `<tr><td lang="${L.lang}" dir="${L.dir}" class="form">${esc(f)}</td><td class="num">${n.toLocaleString("en-GB")}</td><td class="gram">${esc(grammarLabel(code))}</td></tr>`).join("");
  const defHTML = def ? definitionHTML(def) : "";
  const longDef = def.length > 900;

  main.innerHTML = `<div class="screen dict-entry">
    <p class="entry-nav"><button type="button" class="back-btn" data-back>‹ Back</button></p>
    <header class="entry-head">
      <h1 class="entry-lemma" lang="${L.lang}" dir="${L.dir}">${esc(e.lemma)}</h1>
      ${tr ? `<p class="entry-translit">${esc(tr)}</p>` : ""}
      <p class="entry-listen">${sayButton(String(e.lemma || "").split(",")[0].trim(), L.lang === "he" ? "he" : "grc", { label: "Listen" })}</p>
      <p class="entry-tags">
        ${posText ? `<span class="tag">${esc(posText)}</span>` : ""}
        <span class="tag">${aramaic ? "Aramaic" : L.label}</span>
        ${sn ? `<span class="tag">Strong's ${esc(sn)}</span>` : ""}
      </p>
    </header>
    <p class="entry-gloss">${esc(compact(e.gloss) || "—")}</p>
    <p class="entry-count">${total ? `${timesText(total, L.where)}${bookList.length > 1 ? `, in ${bookList.length} books` : ""}` : /^H90\d\d/.test(e.key)
      ? "This is joined to the front or end of other words, so it isn't listed word by word."
      : e.letter === "G" ? "Not in the New Testament. It is in the lexicon because it appears in other Greek writings, such as the Septuagint."
      : "Not tagged in the Hebrew text used here; the lexicon lists it as a related form or spelling."}</p>

    ${forms.length ? `<section class="entry-sec">
      <h2>Forms in the text</h2>
      <table class="forms"><thead><tr><th scope="col">Form</th><th scope="col" class="num">Times</th><th scope="col">Grammar</th></tr></thead>
        <tbody>${formRows(forms.slice(0, 8))}</tbody></table>
      ${forms.length > 8 ? `<p><button type="button" class="btn secondary" data-all-forms>Show all ${forms.length} forms</button></p>` : ""}
    </section>` : ""}

    ${defHTML ? `<section class="entry-sec">
      <h2>Definition</h2>
      <div class="entry-def${longDef ? " clipped" : ""}" lang="en">${defHTML}</div>
      ${longDef ? `<p><button type="button" class="btn secondary" data-full-def aria-expanded="false">Read the full definition</button></p>` : ""}
      <p class="entry-credit">${e.letter === "G"
        ? "From STEPBible's Greek lexicon, based on Abbott-Smith's <em>Manual Greek Lexicon of the New Testament</em> (AS) and the Liddell–Scott lexicon (ML)."
        : "From STEPBible's Hebrew lexicon, based on Brown–Driver–Briggs."}</p>
    </section>` : ""}

    ${siblings.length ? `<section class="entry-sec">
      <h2>Other meanings under ${esc(strongs(e.key.slice(0, 5)))}</h2>
      <p class="muted">STEPBible splits some Strong's numbers into separate meanings or names.</p>
      <ul class="rows">${siblings.map((x) => rowHTML(x)).join("")}</ul>
    </section>` : ""}

    ${total ? `<section class="entry-sec">
      <h2>Every place it appears</h2>
      <p class="muted">Open a book to see each verse. Tap a verse to read it with this word highlighted.</p>
      <div class="occ-books">${bookList.map((b) => {
        const n = occ[b.id].split(" ").length;
        return `<details class="occ-book" data-book="${b.id}"><summary><span>${esc(b.name)}</span><span class="occ-n">${n.toLocaleString("en-GB")}</span></summary><div class="occ-list"></div></details>`;
      }).join("")}</div>
    </section>` : ""}
  </div>`;

  main.querySelector("[data-back]").addEventListener("click", () => nav.goBack("#/words"));
  main.querySelector("[data-all-forms]")?.addEventListener("click", (ev) => {
    main.querySelector(".forms tbody").innerHTML = formRows(forms);
    ev.currentTarget.remove();
  });
  main.querySelector("[data-full-def]")?.addEventListener("click", (ev) => {
    const box = main.querySelector(".entry-def");
    const open = box.classList.toggle("clipped") === false;
    ev.currentTarget.setAttribute("aria-expanded", String(open));
    ev.currentTarget.textContent = open ? "Show less" : "Read the full definition";
  });

  // Every place it appears: each book's verses are drawn when you open it
  const PAGE = 50;
  const fillBook = async (det) => {
    const id = det.dataset.book;
    const list = det.querySelector(".occ-list");
    if (list.dataset.done) return;
    list.dataset.done = "1";
    list.innerHTML = `<p class="muted">Loading…</p>`;
    let text;
    try {
      text = await data.original(id);
    } catch {
      list.innerHTML = `<p class="muted">This book couldn't load. Connect to the internet once and it will be saved for offline use.</p>`;
      delete list.dataset.done;
      return;
    }
    const chapters = new Map(text.ch.map(([c, vs]) => [c, new Map(vs.map((v) => [v[0], v[1]]))]));
    const refs = occ[id].split(" ").map((r) => r.split(".").map(Number));
    const book = books.find((b) => b.id === id);
    let shown = 0;
    const more = () => {
      const slice = refs.slice(shown, shown + PAGE);
      shown += slice.length;
      const html = slice.map(([c, v, wi]) => {
        const words = (chapters.get(c) && chapters.get(c).get(v)) || [];
        const w = words[wi];
        if (!w) return "";
        const gloss = e.letter === "H" ? englishHTML(heEnglish(w[2])) : englishHTML(w[2]);
        const label = v === 0 ? `${c} title` : `${c}:${v}`;
        return `<li><a class="occ" href="#/read/${id}/${c}/${v}/${wi}" data-ref="${esc(`${book.id === "PSA" ? "Psalm" : book.name} ${label}`)}">
          <span class="occ-ref">${label}</span>
          <span class="occ-text" lang="${L.lang}" dir="${L.dir}">${verseLine(e.letter, w, words, wi)}</span>
          <span class="occ-gloss">${gloss || "&nbsp;"}</span></a></li>`;
      }).join("");
      let ul = list.querySelector("ul");
      if (!ul) { list.innerHTML = `<ul class="occ-ul"></ul>`; ul = list.querySelector("ul"); }
      ul.insertAdjacentHTML("beforeend", html);
      list.querySelector("[data-occ-more]")?.remove();
      if (shown < refs.length) {
        list.insertAdjacentHTML("beforeend", `<p><button type="button" class="btn secondary" data-occ-more>Show ${Math.min(PAGE, refs.length - shown)} more of ${(refs.length - shown).toLocaleString("en-GB")}</button></p>`);
        list.querySelector("[data-occ-more]").addEventListener("click", more);
      }
    };
    more();
  };
  main.querySelectorAll(".occ-book").forEach((det) => det.addEventListener("toggle", () => {
    if (det.open) { fillBook(det); entryMemory.open.add(det.dataset.book); } else entryMemory.open.delete(det.dataset.book);
  }));
  main.querySelector(".occ-books")?.addEventListener("click", (ev) => {
    const a = ev.target.closest("a.occ");
    if (!a) return;
    entryMemory.scroll = window.scrollY;
    nav.remember(hash, true);
    nav.offerReturn(a.getAttribute("href"), e.lemma);
  });

  // Coming back from a verse: reopen the same books and scroll position
  if (entryMemory.key === e.key && nav.recall(hash)) {
    const opens = [...main.querySelectorAll(".occ-book")].filter((d) => entryMemory.open.has(d.dataset.book));
    await Promise.all(opens.map((d) => { d.open = true; return fillBook(d); }));
    window.scrollTo(0, entryMemory.scroll);
  } else {
    entryMemory.key = e.key;
    entryMemory.open = new Set();
    // A single book opens straight away
    const dets = main.querySelectorAll(".occ-book");
    if (dets.length === 1) dets[0].open = true;
    window.scrollTo(0, 0);
  }
}

// ---------------------------------------------------------------- the screen

export const words = {
  title: "Words",
  handlesTitle: true,
  handlesScroll: true,
  render(main, params = []) {
    if (params[0]) return renderEntry(main, params[0]);
    return renderSearch(main);
  },
};
