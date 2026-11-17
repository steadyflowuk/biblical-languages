// Pronunciation and audio (Session 9).
// greekSay(): the Erasmian respelling shown in the app ("λόγος" → "LO-gos"), stressed syllable in capitals.
// speechText(): what the phone's own voice is given. Phones have Modern Greek and Israeli Hebrew voices only, so for
// Erasmian the word is respelt in Modern Greek letters that the Greek voice reads with Erasmian sounds
// (β → μπ "b", δ → ντ "d", η → εϊ "ay", υ → ου); for Restored Koine the text is read in modern accents, with the
// first-century vowels the voice has lost written in (η → ε, υ/οι/υι → ιου "yu"). Hebrew: the said shewa sounded.
// speak(): plays it with the phone's voice, or explains how to add one. Pure functions work in Node too (no DOM).

const GREEK_VOWELS = "αεηιουω";
const DIPHTHONGS = ["αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ"];
const ACCENTS = /[́̀͂]/;
const NUCLEUS = { α: "a", ε: "e", η: "ay", ι: "i", ο: "o", υ: "ü", ω: "oh", αι: "ai", ει: "ay", οι: "oi", υι: "wee", αυ: "ow", ευ: "eu", ου: "oo", ηυ: "ayoo" };
const CONSONANT = { β: "b", γ: "g", δ: "d", ζ: "dz", θ: "th", κ: "k", λ: "l", μ: "m", ν: "n", ξ: "x", π: "p", ρ: "r", σ: "s", ς: "s", τ: "t", φ: "f", χ: "kh", ψ: "ps" };

/** Split one Greek word into letters with their marks: [{ ch, rough, accent, diaeresis }]. */
function letters(word) {
  const out = [];
  for (const c of String(word).normalize("NFD").toLowerCase()) {
    if (/[̀-ͯͅ]/.test(c)) {
      const last = out[out.length - 1];
      if (!last) continue;
      if (c === "̔") last.rough = true;
      else if (ACCENTS.test(c)) last.accent = true;
      else if (c === "̈") last.diaeresis = true;
      continue; // smooth breathing and iota subscript are silent
    }
    if (GREEK_VOWELS.includes(c) || CONSONANT[c]) out.push({ ch: c });
  }
  return out;
}

/**
 * One word as syllables: [{ onset: [greek consonants], nucleus: "ει", coda: [...], stress, rough }]
 * English-style division (as taught in the lessons): one consonant between vowels starts the next syllable; of two or
 * more, the first closes the syllable before (pis-TEU-o-men, AN-throh-pos, ek-klay-SEE-a). ξ is split k|s (DOK-sa).
 */
export function greekSyllables(word) {
  const L = letters(word);
  const units = []; // vowel nuclei and consonants in order
  for (let i = 0; i < L.length; i++) {
    const a = L[i];
    if (GREEK_VOWELS.includes(a.ch)) {
      const b = L[i + 1];
      if (b && GREEK_VOWELS.includes(b.ch) && DIPHTHONGS.includes(a.ch + b.ch) && !b.diaeresis && !a.accent) {
        units.push({ v: a.ch + b.ch, accent: !!(a.accent || b.accent), rough: !!(a.rough || b.rough) });
        i++;
      } else units.push({ v: a.ch, accent: !!a.accent, rough: !!a.rough });
    } else if (a.ch === "ρ") units.push({ c: "ρ" }); // ῥ: the breathing isn't sounded
    else units.push({ c: a.ch });
  }
  const syl = [];
  let pending = [];
  units.forEach((u, i) => {
    if (u.c) { pending.push(u.c); return; }
    if (syl.length) {
      // share the consonants between the previous syllable and this one
      // π β κ γ τ δ before λ or ρ, and φ θ χ before ρ, stay together (PE-tros, a-po-KREE-noh, bi-BLEE-on);
      // otherwise the first consonant closes the syllable (OKH-los, KOS-mos, TEK-non)
      const together = pending.length === 2 && ((/[πβκγτδ]/.test(pending[0]) && /[λρ]/.test(pending[1])) || (/[φθχ]/.test(pending[0]) && pending[1] === "ρ"));
      let give = pending.length >= 2 && !together ? 1 : 0;
      if (pending.length === 1 && pending[0] === "ξ") { // δόξα → dok-sa
        syl[syl.length - 1].coda.push("κ");
        pending = ["σ"];
      }
      syl[syl.length - 1].coda.push(...pending.slice(0, give));
      pending = pending.slice(give);
    }
    syl.push({ onset: pending, nucleus: u.v, coda: [], stress: u.accent, rough: u.rough });
    pending = [];
  });
  if (syl.length) syl[syl.length - 1].coda.push(...pending);
  return syl;
}

const latinConsonants = (cs) => cs.map((c, i) => (c === "γ" && /[γκχξ]/.test(cs[i + 1] || "") ? "n" : CONSONANT[c])).join("");

// Elision: a word cut to a lone consonant (δ᾽ = δέ) is said with the word after it (δ᾽ ἂν → "dan"); on its own it
// gets its ε back so there is something to say. Longer cut words (ἀλλ᾽, κατ᾽) keep their own syllable.
const ELIDED = /(^|\s)([βγδθκλμνπρστφχ])[’'᾽ʼ]\s+(?=[Ͱ-Ͽἀ-῿])/g;
const ELIDED_ALONE = /(^|\s)([δτμγ])[’'᾽ʼ](?=[\s,.;:·]|$)/g;
const unElide = (text) => String(text || "").replace(ELIDED, "$1$2").replace(ELIDED_ALONE, "$1$2ε");

/** Erasmian respelling of Greek text, word by word: "ἐν ἀρχῇ" → "en ar-KHAY". */
export function greekSay(text) {
  return unElide(text).replace(/[’'᾽ʼ]/g, "").split(/[\s,.;:·!?()“”]+/).filter((w) => /[Ͱ-Ͽἀ-῿]/.test(w)).map((w) => {
    const syl = greekSyllables(w);
    const parts = syl.map((s, i) => {
      // γ before γ κ χ ξ in the next syllable is "n" (ἄγγελος ANG-ge-los)
      const next = syl[i + 1];
      const coda = s.coda.map((c, j) => {
        const follow = s.coda[j + 1] || (next && next.onset[0]) || "";
        if (c !== "γ" || !/[γκχξ]/.test(follow)) return CONSONANT[c];
        return follow === "γ" ? "ng" : "n"; // γγ: ANG-ge-los; γκ, γχ: n
      }).join("");
      let v = NUCLEUS[s.nucleus] || "";
      if (s.nucleus === "ι" && !s.coda.length && (s.stress || (next && !next.onset.length))) v = "ee"; // KÜ-ree-os, dee-A
      if (s.nucleus === "υι" && s.rough) v = "wee";
      const h = s.rough && i === 0 && !s.onset.length ? "h" : "";
      return h + latinConsonants(s.onset) + v + coda;
    });
    if (parts.length > 1) {
      const k = syl.findIndex((s) => s.stress);
      if (k >= 0) parts[k] = parts[k].toUpperCase();
    }
    return parts.join("-");
  }).join(" ");
}

// ---------------------------------------------------------------- what the phone's voice reads

const TONOS = { α: "ά", ε: "έ", η: "ή", ι: "ί", ο: "ό", υ: "ύ", ω: "ώ" };
// Erasmian sounds written in Modern Greek letters. The first letter takes the stress mark (έι is "ay", as in κέικ).
const SPEECH_VOWEL = { α: "α", ε: "ε", η: "ει", ι: "ι", ο: "ο", υ: "ου", ω: "ο", αι: "αι", ει: "ει", οι: "οι", υι: "ουι", αυ: "αου", ευ: "εου", ου: "ου", ηυ: "ειου" };
const SPEECH_CONSONANT = { β: "μπ", γ: "γκ", δ: "ντ", ζ: "τζ" };
const DIGRAPHS = /^(αι|ει|οι|ου|αυ|ευ|υι)$/;

function speechVowel(nucleus, stressed, afterVowel) {
  let v = SPEECH_VOWEL[nucleus] || nucleus;
  if (v === "ουι") return stressed ? "ουί" : "ουι";
  if (v.length === 2 && !v.startsWith("ου")) {
    // two separate sounds (ay, ai, oi): stress the first letter, or put a diaeresis on the second so it isn't merged
    return stressed ? TONOS[v[0]] + v[1] : v[0] + { ι: "ϊ", υ: "ϋ" }[v[1]];
  }
  if (v === "αου" || v === "εου") return stressed ? TONOS[v[0]] + "ου" : v[0] + "ου";
  if (v === "ειου") return stressed ? "έιου" : "εϊου";
  if (v === "ου") return stressed ? "ού" : "ου";
  if (afterVowel && /^[ιυ]$/.test(v)) return stressed ? { ι: "ΐ", υ: "ΰ" }[v] : { ι: "ϊ", υ: "ϋ" }[v]; // keep it separate (πρωΐ, Δαυίδ)
  return stressed ? TONOS[v] || v : v;
}

/** Greek respelt so a Modern Greek voice says it the Erasmian way: "λόγος" → "λόγκος", "ἀγάπη" → "αγκάπεϊ". */
export function erasmianSpeech(text) {
  // NFC turns the Greek question mark (U+037E) into ; and the raised dot (U+0387) into ·
  return unElide(String(text || "").normalize("NFC")).replace(/[’'᾽ʼ()[\]⟦⟧]/g, "").split(/\s+/).map((w) => {
    const punct = (w.match(/[,.;:·!?—–]+$/) || [""])[0].replace(/[·—–]/g, ",").replace(/;/g, "?").replace(/([.?!]),+$/, "$1").replace(/,+/g, ",");
    const syl = greekSyllables(w);
    if (!syl.length) return "";
    const one = syl.length === 1;
    let out = "";
    let before = ""; // the Greek consonant just written, across syllables
    syl.forEach((s, i) => {
      const cons = (cs, nextFirst) => cs.map((c, j) => {
        const follow = cs[j + 1] || nextFirst || "";
        const prev = j ? cs[j - 1] : before;
        before = c;
        if (c === "γ" && /[γκχξ]/.test(follow)) return "γ"; // γγ, γκ: already "ng", "nk" in Modern Greek
        if (c === "γ" && prev === "γ") return "γ";
        if (c === prev && SPEECH_CONSONANT[c]) return ""; // a doubled β or δ: μπ, ντ once (Φεννεδδώρ)
        return SPEECH_CONSONANT[c] || c;
      }).join("");
      const next = syl[i + 1];
      const onset = cons(s.onset, s.nucleus);
      if (!s.onset.length) before = "";
      const prevEndsVowel = !!out && /[αεηιουωάέήίόύώϊϋ]$/.test(out) && !s.onset.length;
      out += onset + speechVowel(s.nucleus, s.stress || one, prevEndsVowel); // one syllable: the mark keeps "ay" one sound
      before = "";
      out += cons(s.coda, next && next.onset[0]);
    });
    return out.replace(/σ$/, "ς") + punct;
  }).filter(Boolean).join(" ");
}

// Restored Koine vowels that Modern Greek has lost. A Modern Greek voice reading the text as written says η, υ, οι
// and υι all as "ee"; in the first century η was still "e" and υ, οι, υι were "ü" (as the Letters guide teaches).
// So η is written ε (ηυ then reads ev/ef, like ευ), and ü is written ιου, the way Greek writes ü in foreign names
// (the nearest sound a Modern Greek voice has). αυ, ευ and ου stay as they are: their Koine sounds are the modern ones.
function koineVowels(word) {
  const c = [...word];
  let out = "";
  // ü as ιου; after a vowel as ϊου, or the ι would join that vowel into a pair (θεοί → θεϊού, not θειού "thi-u")
  const yu = (stressed) => (/[αεουάέόύ]$/.test(out) ? "ϊ" : "ι") + (stressed ? "ού" : "ου");
  for (let i = 0; i < c.length; i++) {
    const a = c[i], b = c[i + 1] || "";
    if (/[αεηο]/.test(a) && /[υύ]/.test(b)) { out += (a === "η" ? "ε" : a) + b; i++; continue; } // αυ ευ ηυ ου
    if (/[ου]/.test(a) && /[ιί]/.test(b)) { out += yu(b === "ί"); i++; continue; } // οι υι
    if (/[υϋ]/.test(a)) { out += yu(false); continue; }
    if (/[ύΰ]/.test(a)) { out += yu(true); continue; }
    if (a === "η" || a === "ή") {
      out += a === "ή" ? "έ" : "ε";
      if (b === "ι" || b === "ί") { out += b === "ί" ? "ΐ" : "ϊ"; i++; } // νηί: ε then i, two sounds (not ει "i")
      continue;
    }
    out += a;
  }
  // a one-letter word keeps a stress mark so it is said as a vowel, not a letter name (ἡ → έ)
  // a word of one vowel that the change made new keeps a stress mark, so it is said as a word (ἡ → έ, οἱ → ιού)
  return out === "ε" ? "έ" : out === "ιου" ? "ιού" : out;
}

/** Greek for the voice in Restored Koine: modern accents, no breathings, and the Koine sounds of η, υ, οι and υι. */
export function koineSpeech(text) {
  return unElide(text).replace(/[[\]()⟦⟧]/g, "").replace(/=/g, " ").normalize("NFD")
    .replace(/[̓̔ͅ]/g, "") // breathings, iota subscript
    .replace(/[̀͂]/g, "́") // grave and circumflex become acute (tonos)
    .replace(/·/g, ",").replace(/;/g, "?").replace(/[—–]/g, ",").replace(/([.?!]),/g, "$1").replace(/,,+/g, ",").replace(/[’᾽ʼ]/g, "")
    .normalize("NFC").toLowerCase()
    .replace(/[Ͱ-Ͽ]+/g, koineVowels);
}

// The divine name with any points, alone or after a one-letter prefix (with its vowel): read Adonai, as is customary;
// with hiriq (after Adonai, "Lord GOD") it is read Elohim.
const POINTS = "[ְ-ׇ]*";
const DIVINE_NAME = new RegExp("(^|[^ְ-ׇא-ת])((?:[ובכלמהש]" + POINTS + "){0,2})י" + POINTS + "ה" + POINTS + "ו" + POINTS + "ה" + POINTS + "(?![ְ-ׇא-ת])", "g");
const ADONAI = "אֲדֹנָי";
const ELOHIM = "אֱלֹהִים";

// The app teaches the said (vocal) shewa as a quick e (be-RIT, de-va-RIM, yish-me-RU); an Israeli voice usually drops
// it (brit, dvarim). In the voice text a said shewa becomes segol, so the voice says the e. A shewa is said:
// under a word's first letter; after another shewa (the second of two); after a long vowel (holam, tsere, shureq —
// so after the conjunction וּ too —, hiriq or tsere with yod, a qamets with meteg); under a doubled letter (dagesh
// after a vowel); and before the same letter (hal-le-LU). Never at the end of a word (nor before a final silent א),
// and a plain shewa under a throat letter is silent. The other shewas (closing a syllable) stay silent, as taught.
const SHEWA = "ְ", SEGOL = "ֶ", DAGESH = "ּ", METEG = "ֽ", QAMATS = "ָ", HOLAM = "ֹ", QQATAN = "ׇ";
const FULL_VOWEL = /[ֱ-ׇֻ]/;
const THROAT = /[אהחע]/;
const VAV_VOWEL = /^וּֽ?$/; // וּ, with or without a meteg
const marksOnly = (c) => c.replace(/[֑-ֽֿׅ֯ׄ]/g, ""); // a cluster without accents, meteg and rafe

/** A word as clusters (a letter and the marks on it), or null if it holds anything else. */
function clusters(word) {
  const cl = word.match(/[א-ת][֑-ׇ]*/g);
  return cl && cl.join("") === word ? cl : null;
}

function saidShewa(word) {
  const cl = clusters(word);
  if (!cl || cl.length < 2) return word; // anything unusual: leave it
  return cl.map((c, i) => {
    if (!c.includes(SHEWA)) return c;
    if (FULL_VOWEL.test(c)) return c.replace(SHEWA, ""); // a shewa beside another vowel (a slip in the source): the vowel wins
    if (i === cl.length - 1 || (i && THROAT.test(c[0]))) return c;
    if (i === cl.length - 2 && cl[i + 1] === "א") return c; // before a final silent א (אַרְתַּחְשַׁסְתְּא)
    const prev = cl[i - 1] || "";
    const p0 = marksOnly(prev);
    const afterVowel = !!prev && !prev.includes(SHEWA) && (FULL_VOWEL.test(prev) || VAV_VOWEL.test(p0) || /^[אהוי]$/.test(p0));
    // a long vowel before it: holam, tsere, shureq, hiriq or tsere with yod, a qamets with meteg (וַיֹּאמְרוּ, יָֽשְׁבוּ)
    const before = cl[i - 2] || "";
    const v = p0 === "א" ? before : prev; // a silent א: the vowel is on the letter before (וַיֹּאמְרוּ)
    const afterLong = !!prev && !v.includes(SHEWA) && (/[ֵֹ]/.test(v) || VAV_VOWEL.test(marksOnly(v))
      || (v.includes(QAMATS) && v.includes(METEG)) || (p0 === "י" && /[ִֵ]/.test(before)));
    const said = i === 0 || prev.includes(SHEWA) || afterLong || (c.includes(DAGESH) && afterVowel) || cl[i + 1][0] === c[0];
    return said ? c.replace(SHEWA, SEGOL) : c;
  }).join("");
}

// accents written away from the stressed syllable: pashta, segolta, zarqa, telisha qetanna (after it); telisha
// gedola, yetiv, dehi (before it)
const OFF_STRESS = /[֚֭֮֙֒֩֠]/; // + dehi, written before the stressed syllable in the poetic books
const ACCENT = /[֑-֯]/;

/** The cluster holding a qamets in a word's closed last syllable (then a final consonant, not a silent ה or א), or -1. */
function lastClosedQamets(cl) {
  const n = cl.length;
  if (n < 2) return -1;
  const q = cl[n - 2], last = cl[n - 1];
  const only = marksOnly(q).replace(/[א-תּׁׂ]/g, "") === QAMATS; // the qamets is its only vowel
  const silent = (last[0] === "ה" && !last.includes(DAGESH)) || last[0] === "א";
  return only && !FULL_VOWEL.test(last) && !silent ? n - 2 : -1;
}
/** Is the word's accent on a syllable before its last one? (Only accents written on the stressed syllable count.) */
function stressedEarlier(cl) {
  const at = cl.map((c, i) => (ACCENT.test(c) && !OFF_STRESS.test(c) ? i : -1)).filter((i) => i >= 0);
  return at.length > 0 && Math.max(...at) < cl.length - 2;
}

/**
 * Qamets hatuf the voice can't know (it reads every qamets "a"): a qamets in a closed syllable that isn't stressed is a
 * short o. Here only the cases the spelling itself settles:
 *  • כָּל kol (spelt with qamets it is always kol), with up to two prefixes (וּבְכָל־);
 *  • a qamets before a hateph qamets (אָהֳלוֹ o-ho-LO, מָחֳרָת mo-cho-RAT), except the article's (בָּאֳנִי ba-o-NI);
 *  • a wayyiqtol whose accent falls before its last syllable (וַיָּ֖מָת va-YA-mot, וַתָּ֣קָם va-TA-kom).
 * Other verbs (זְכָר־ ze-khor, יִשְׁמָר־ yish-mor) need the word's grammar: verbHatuf(), called by audio.heVoice().
 * A noun keeps its long qamets there (אָ֣דָם A-dam, הָעָם־ ha-am), and a qamets before a shewa can be either
 * (qa-te-LU, chokh-MAH), so those are left to the voice. word: accents still on; joined: a maqqef follows.
 */
function qametsHatuf(word, joined) {
  const cl = clusters(word);
  if (!cl) return word;
  const only = (c) => marksOnly(c).replace(/[א-תּׁׂ]/g, "") === QAMATS;
  cl.forEach((c, i) => {
    const article = i === 0 && /[בכלה]/.test(c[0]);
    if (only(c) && !article && cl[i + 1] && cl[i + 1].includes("ֳ")) cl[i] = c.replace(QAMATS, QQATAN);
  });
  // a qamets before a throat letter with a plain shewa: that shewa is silent (a said one would be hateph), so the
  // syllable is closed: רָחְבּוֹ roch-BO, יָהְדָּי yoh-DAI (not when the qamets carries a meteg or the accent)
  cl.forEach((c, i) => {
    const next = cl[i + 1];
    if (only(c) && !c.includes(METEG) && !ACCENT.test(c) && next && THROAT.test(next[0]) && next.includes(SHEWA) && !FULL_VOWEL.test(next) && i + 1 < cl.length - 1) cl[i] = c.replace(QAMATS, QQATAN);
  });
  const q = lastClosedQamets(cl);
  if (q >= 0) {
    const kol = cl[q][0] === "כ" && cl[q + 1][0] === "ל" && cl.length <= 4
      && cl.slice(0, q).every((c) => /[ובכלמהש]/.test(c[0]));
    // וַ then a prefix letter with dagesh (יּ תּ נּ), or וָא: the "and" of a wayyiqtol
    const wayyiqtol = /^ו[֑-ֽ֯]*ַ/.test(cl[0]) && cl[1] && cl[1].includes(DAGESH) && /[יתנ]/.test(cl[1][0])
      || (/^ו[֑-ֽ֯]*ָ/.test(cl[0]) && cl[1] && cl[1][0] === "א");
    if (kol || (wayyiqtol && (joined || stressedEarlier(cl)))) cl[q] = cl[q].replace(QAMATS, QQATAN);
  }
  return cl.join("");
}

/**
 * For a verb (the caller knows its grammar): the qamets of a closed last syllable that isn't stressed — the word is
 * joined by maqqef, or stressed earlier — is qamets hatuf (זְכָר־ ze-khor, לִשְׁבָּר־ lish-bor, יִשְׁמָר־ yish-mor).
 * Marks it with the qamets hatuf sign ׇ, which hebrewSpeech reads o.
 */
export function verbHatuf(word, joined, form) {
  const cl = clusters(word);
  if (!cl) return word;
  const q = lastClosedQamets(cl);
  if (q >= 0 && (joined || stressedEarlier(cl))) cl[q] = cl[q].replace(QAMATS, QQATAN);
  // a qamets before a shewa (no meteg): a Qal perfect keeps the long a and says the shewa (שָׁמְרוּ sha-me-RU); a Qal
  // imperative or infinitive has qamets hatuf and a silent shewa (שָׁמְרֵנִי shom-RE-ni). form: "p", "v", "c" or "".
  if (form) {
    const only = (c) => marksOnly(c).replace(/[א-תּׁׂ]/g, "") === QAMATS;
    const i = cl.findIndex((c, k) => only(c) && !c.includes(METEG) && cl[k + 1] && cl[k + 1].includes(SHEWA) && !FULL_VOWEL.test(cl[k + 1]) && k + 1 < cl.length - 1);
    if (i >= 0 && form === "p" && !THROAT.test(cl[i + 1][0])) cl[i + 1] = cl[i + 1].replace(SHEWA, SEGOL);
    if (i >= 0 && (form === "v" || form === "c")) cl[i] = cl[i].replace(QAMATS, QQATAN);
  }
  return cl.join("");
}

/**
 * Words the scribes always read differently from how they are written, spelt for the voice as they are read:
 *  • הִוא (written "hu", pointed and read hi, "she", 191 times in the Torah) → הִיא, or the voice says hu;
 *  • a letter carrying hiriq with patah or qamets (יְרוּשָׁלִַם, read ye-ru-sha-LA-yim) → that vowel, then yod with hiriq;
 *  • an unpointed ש inside a word (יִשָּׂשכָר, read yis-sa-KHAR) is silent → left out.
 */
function perpetualQere(word) {
  return word
    .replace(/הִ(ֽ?)וא$/, "הִ$1יא")
    .replace(/([א-ת][ּֽֿׁׂ]*)(?:([ַָ])ֽ?ִ|ִֽ?([ַָ]))ֽ?/g, (m, l, a, b) => l + (a || b) + "יִ")
    .replace(/([ְ-ׇ])ש(?=[א-ת])/g, "$1"); // (no look-behind: older iPhones can't read it)
}

/**
 * Hebrew for the Israeli voice: no cantillation or meteg; the divine name read as Adonai (as is customary); the said
 * shewa sounded; the sure cases of qamets hatuf read o; and the verse's main pauses heard — a comma at the atnah (and
 * segolta), the verse's middle, and a full stop at sof pasuq ׃, its end.
 */
export function hebrewSpeech(text) {
  const out = [];
  String(text || "").replace(/[/[\]]/g, "").replace(/׃/g, "׃ ").split(/\s+/).forEach((token) => {
    if (!token || /^[פס]$/.test(token)) return; // paragraph letters standing alone (not a word's last letter: סוּס)
    const parts = token.split("־");
    parts.forEach((raw, k) => {
      const joined = k < parts.length - 1;
      const stop = /׃/.test(raw) ? "." : /[֑֒]/.test(raw) ? "," : "";
      let w = raw.replace(/[׀׃׆]/g, ""); // paseq, sof pasuq, inverted nun
      if (!/[א-ת]/.test(w)) { if (stop && out.length) out[out.length - 1] += stop; return; }
      w = qametsHatuf(w, joined)
        .replace(/[֑-֯]/g, ""); // accents (the meteg stays for saidShewa)
      w = perpetualQere(w)
        .replace(DIVINE_NAME, (m, start, prefix) => start + prefix + (/ִ/.test(m.slice(prefix.length)) ? ELOHIM : ADONAI));
      // a shewa after qamets hatuf (ׇ, short) stays silent: חׇכְמָה chokh-MAH; then ׇ becomes holam, which every voice knows
      w = saidShewa(w).replace(/[ֽֿׅׄ]/g, "").replace(/ׇ/g, HOLAM); // meteg, rafe, the scribes' dots
      out.push(w + stop);
    });
  });
  // a word on its own needs no pause after it
  if (out.length === 1) return out[0].replace(/[,.]$/, "");
  return out.join(" ").replace(/,$/, ""); // nothing follows the last word: no pause to make
}

/**
 * A Hebrew word whose pronunciation the app shows (a card's "say", e.g. "chokh-MAH"): where the respelling has o for a
 * qamets, that qamets is qamets hatuf, so it is marked ׇ for the voice. The spelling alone can't tell qa-te-LU from
 * chokh-MAH; the respelling, checked by hand, can.
 */
export function hebrewForSay(text, say) {
  const cl = clusters(String(text || "").trim());
  if (!cl || !say) return text;
  const slots = [];
  cl.forEach((c, i) => {
    const m = marksOnly(c);
    if (/^ו[ֹּ]$/.test(m) && i > 0 && !FULL_VOWEL.test(marksOnly(cl[i - 1])) && !cl[i - 1].includes(SHEWA)) { slots.push({ v: m.includes(HOLAM) ? "o" : "u" }); return; }
    if (m.includes(QAMATS)) { slots.push({ v: "a", q: i }); return; }
    const v = [["ֱ", "e"], ["ֲ", "a"], ["ֳ", "o"], ["ִ", "i"], ["ֵ", "e"], ["ֶ", "e"], ["ַ", "a"], [HOLAM, "o"], ["ֺ", "o"], ["ֻ", "u"], [QQATAN, "o"]].find(([k]) => m.includes(k));
    if (v) slots.push({ v: v[1] });
    else if (m.includes(SHEWA) && i < cl.length - 1) slots.push({ v: "e", opt: true, c: i });
  });
  const said = (String(say).toLowerCase().replace(/ch|kh|sh|ts/g, "c").replace(/([aeou])[iy](?=$|[^aeiou]|-)/g, "$1").match(/[aeiou]/g)) || [];
  // line the vowel slots up with the respelling's vowels (both are short: plain edit distance)
  const n = slots.length, m = said.length;
  const D = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  const fit = (s, v) => s.v === v || (s.q != null && v === "o");
  for (let i = 1; i <= n; i++) D[i][0] = D[i - 1][0] + (slots[i - 1].opt ? 0 : 1);
  for (let j = 1; j <= m; j++) D[0][j] = j;
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
    D[i][j] = Math.min(D[i - 1][j - 1] + (fit(slots[i - 1], said[j - 1]) ? 0 : 1), D[i - 1][j] + (slots[i - 1].opt ? 0 : 1), D[i][j - 1] + 1);
  }
  for (let i = n, j = m; i > 0 && j > 0;) {
    if (D[i][j] === D[i - 1][j - 1] + (fit(slots[i - 1], said[j - 1]) ? 0 : 1)) {
      const s = slots[i - 1];
      if (s.q != null && said[j - 1] === "o") cl[s.q] = cl[s.q].replace(QAMATS, QQATAN);
      if (s.opt && said[j - 1] === "e") cl[s.c] = cl[s.c].replace(SHEWA, SEGOL); // ka-te-LU: the respelling says this shewa
      i--; j--;
    } else if (D[i][j] === D[i - 1][j] + (slots[i - 1].opt ? 0 : 1)) i--;
    else j--;
  }
  return cl.join("");
}

/** The text a voice should read for a word or phrase, by language and pronunciation setting. */
export function speechText(text, lang, greekVoice) {
  if (lang === "he") return hebrewSpeech(text);
  return greekVoice === "koine" ? koineSpeech(text) : erasmianSpeech(text);
}

// ---------------------------------------------------------------- playing it (browser only)

const VOICE_LANG = { grc: ["el"], he: ["he", "iw"] };

/** The phone's voice for a language, or null. Voices load late on some phones, so ask again each time. */
export function voiceFor(lang) {
  if (typeof speechSynthesis === "undefined") return null;
  const voices = speechSynthesis.getVoices() || [];
  const want = VOICE_LANG[lang] || [];
  const fits = voices.filter((v) => want.some((p) => String(v.lang || "").toLowerCase().replace("_", "-").startsWith(p)));
  return fits.find((v) => v.localService) || fits[0] || null;
}

export const canSpeak = () => typeof speechSynthesis !== "undefined" && typeof SpeechSynthesisUtterance !== "undefined";

let current = null; // keep the utterance referenced until it ends (Chrome can drop it otherwise)

/**
 * Say text aloud, at once: phones only allow speech that starts inside the tap itself, so nothing here waits.
 * Returns { ok: true, text } or { ok: false, why: "unsupported" | "no-voice" }.
 * options: { lang: "grc"|"he", greekVoice, rate: "slow"|"normal", onstart, onend, onfail }
 * If the phone hasn't listed its voices yet, the language alone is set and the phone picks a voice; onfail runs if
 * nothing has started after a few seconds (no voice for that language, in practice).
 */
export function speak(text, options) {
  const o = options || {};
  if (!canSpeak()) return { ok: false, why: "unsupported" };
  const listed = speechSynthesis.getVoices() || [];
  const voice = voiceFor(o.lang);
  if (!voice && listed.length) return { ok: false, why: "no-voice" };
  if (speechSynthesis.speaking || speechSynthesis.pending) speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(speechText(text, o.lang, o.greekVoice));
  if (voice) u.voice = voice;
  u.lang = voice ? voice.lang : o.lang === "he" ? "he-IL" : "el-GR";
  u.rate = o.rate === "normal" ? 1 : 0.75;
  let started = false;
  let finished = false;
  u.onstart = () => { started = true; if (o.onstart) o.onstart(); };
  u.onend = u.onerror = () => { finished = true; if (current === u) current = null; if (o.onend) o.onend(); };
  current = u;
  speechSynthesis.speak(u);
  if (!voice && o.onfail) setTimeout(() => { if (!started && !finished && current === u) { speechSynthesis.cancel(); o.onfail(); } }, 3000);
  return { ok: true, text: u.text };
}

/** Ask the phone for its voices early, so the first tap can pick the right one. */
export function warmUpVoices() {
  if (!canSpeak()) return;
  try { speechSynthesis.getVoices(); speechSynthesis.addEventListener("voiceschanged", () => speechSynthesis.getVoices()); } catch (e) { /* older engines */ }
}

export const stopSpeaking = () => { if (canSpeak()) speechSynthesis.cancel(); };
