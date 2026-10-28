// Pronunciation and audio (Session 9).
// greekSay(): the Erasmian respelling shown in the app ("λόγος" → "LO-gos"), stressed syllable in capitals.
// speechText(): what the phone's own voice is given. Phones have Modern Greek and Israeli Hebrew voices only, so for
// Erasmian the word is respelt in Modern Greek letters that the Greek voice reads with Erasmian sounds
// (β → μπ "b", δ → ντ "d", η → εϊ "ay", υ → ου); for Restored Koine the text is read as written, in modern accents.
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

/** Erasmian respelling of Greek text, word by word: "ἐν ἀρχῇ" → "en ar-KHAY". */
export function greekSay(text) {
  return String(text || "").replace(/[’'᾽ʼ]/g, "").split(/[\s,.;:·!?()“”]+/).filter((w) => /[Ͱ-Ͽἀ-῿]/.test(w)).map((w) => {
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
      const h = s.rough && i === 0 ? "h" : "";
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
  if (afterVowel && /^[ιυ]$/.test(v)) v = { ι: "ϊ", υ: "ϋ" }[v]; // keep a vowel after a vowel separate
  return stressed ? TONOS[v] || v : v;
}

/** Greek respelt so a Modern Greek voice says it the Erasmian way: "λόγος" → "λόγκος", "ἀγάπη" → "αγκάπεϊ". */
export function erasmianSpeech(text) {
  return String(text || "").replace(/[’'᾽ʼ]/g, "").split(/\s+/).map((w) => {
    const punct = (w.match(/[,.;:·!?]+$/) || [""])[0].replace(/·/g, ",").replace(/;/g, "?");
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

/** Greek in modern accents, read as written (Restored Koine is close to Modern Greek): no breathings, one accent mark. */
export function koineSpeech(text) {
  return String(text || "").normalize("NFD")
    .replace(/[̓̔ͅ]/g, "") // breathings, iota subscript
    .replace(/[̀͂]/g, "́") // grave and circumflex become acute (tonos)
    .replace(/·/g, ",").replace(/;/g, "?").replace(/[’᾽ʼ]/g, "")
    .normalize("NFC");
}

// The divine name with any points, alone or after a one-letter prefix (with its vowel): read Adonai, as is customary;
// with hiriq (after Adonai, "Lord GOD") it is read Elohim.
const POINTS = "[ְ-ׇ]*";
const DIVINE_NAME = new RegExp("(^|[^ְ-ׇא-ת])((?:[ובכלמה]" + POINTS + ")?)י" + POINTS + "ה" + POINTS + "ו" + POINTS + "ה" + POINTS + "(?![ְ-ׇא-ת])", "g");
const ADONAI = "אֲדֹנָי";
const ELOHIM = "אֱלֹהִים";

/** Hebrew for the Israeli voice: no cantillation or meteg, and the divine name read as Adonai, as is customary. */
export function hebrewSpeech(text) {
  return String(text || "").replace(/\//g, "")
    .replace(/[֑-ֽ֯׀׃׆]/g, "") // accents, meteg, paseq, sof pasuq, inverted nun
    .replace(/[פס](?=\s|$)/g, "")
    .replace(DIVINE_NAME, (m, start, prefix) => start + prefix + (/ִ/.test(m.slice(prefix.length)) ? ELOHIM : ADONAI))
    .replace(/־/g, " ").replace(/\s+/g, " ").trim();
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
 * options: { lang: "grc"|"he", greekVoice, rate: "slow"|"normal", onend, onfail }
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
  u.onstart = () => { started = true; };
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
