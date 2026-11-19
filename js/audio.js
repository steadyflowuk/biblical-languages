// Listen buttons (Session 9): <button data-say="λόγος" data-say-lang="grc">. One click handler for the whole app
// (bound in app.js), so any screen can drop in sayButton() without wiring. Speech itself lives in sound.js.
import * as store from "./store.js";
import { speak, speechText, canSpeak, stopSpeaking, warmUpVoices, hebrewByGrammar, hebrewForSay } from "./sound.js";
import { heText, heJoined, heMainKey } from "./hebrew.js";

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const ICON = `<svg class="say-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path class="say-wave" d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>`;

/**
 * A listen button. text: the Greek or Hebrew to say; lang: "grc" | "he".
 * options.label: visible words next to the icon (default none: icon only, named for screen readers).
 * options.name: the name screen readers give an icon-only button (default "Listen: " and the text).
 * options.say: the pronunciation shown beside a Hebrew word ("chokh-MAH"): it settles qamets hatuf for the voice.
 */
export function sayButton(text, lang, options) {
  const o = options || {};
  // nothing a voice could say (a lone paragraph mark, a dash): no button
  if (!text || !/[א-ת\u0370-\u03FF\u1F00-\u1FFF]/.test(speechText(text, lang === "he" ? "he" : "grc"))) return "";
  const name = o.label || "Listen";
  if (o.say && lang === "he") text = hebrewForSay(text, o.say);
  return `<button type="button" class="say-btn${o.label ? " with-label" : ""}${o.className ? " " + o.className : ""}" data-say="${esc(text)}" data-say-lang="${lang === "he" ? "he" : "grc"}" aria-label="${esc(o.label ? name : o.name ? o.name : `${name}: ${text}`)}">${ICON}${o.label ? `<span>${esc(o.label)}</span>` : ""}</button>`;
}

function platform() {
  const ua = navigator.userAgent || "";
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "ios";
  if (/Android/.test(ua)) return "android";
  return "other";
}

/** How to add a voice, in the learner's words. */
export function voiceHelp(lang) {
  const language = lang === "he" ? "Hebrew" : "Greek";
  const p = platform();
  if (p === "ios") return `Your iPhone or iPad needs a ${language} voice: open Settings, then Accessibility › Spoken Content › Voices › ${language}, and download one. Then come back and tap Listen again.`;
  if (p === "android") return `Your phone needs a ${language} voice: open Settings and search for “Text-to-speech”, open the speech engine's settings, then install the ${language} voice data. Then come back and tap Listen again.`;
  return `This device has no ${language} voice. Add one in its speech settings (often under Accessibility or Language), then tap Listen again.`;
}

function notice(message) {
  document.querySelector(".toast")?.remove();
  const el = document.createElement("div");
  el.className = "toast toast-long";
  el.setAttribute("role", "status");
  el.textContent = message;
  document.body.append(el);
  setTimeout(() => el.remove(), 9000);
}

let playing = null;

/** Say what a [data-say] button holds; the button shows it's playing until the voice finishes. */
export function play(button) {
  return sayText(button.dataset.say, button.dataset.sayLang, button);
}

/** Say text at once (call it inside a tap); button, if given, shows it's playing until the voice finishes. */
export function sayText(text, lang, button, quiet) {
  if (playing) playing.classList.remove("playing");
  playing = button || null;
  if (button) button.classList.add("playing");
  const done = () => { if (button) button.classList.remove("playing"); if (button && playing === button) playing = null; };
  // no waiting before speak(): phones only allow speech that starts inside the tap
  const r = speak(text, {
    lang, greekVoice: store.get("greekVoice"), rate: store.get("speechRate"), onend: done,
    onfail: () => { done(); if (!quiet) notice(voiceHelp(lang)); },
  });
  if (!r.ok) {
    done();
    if (!quiet) notice(r.why === "no-voice" ? voiceHelp(lang) : "This browser can't speak words aloud. Try the app in Safari on an iPhone or iPad, or Chrome on Android.");
  }
  return r;
}

// ---------------------------------------------------------------- listening practice (17 Nov 2026)
// Settings › Listening practice decides how verses can be heard (Today, a lesson's verse, the Reader, the Septuagint,
// the Letters guide's verses to read aloud):
//   easy   — tap any word to hear it on its own;
//   medium — tap any word to hear it, or hear the whole verse;
//   hard   — hear the whole verse only (tapping a word still shows what it means, without saying it).

export function listenLevel() {
  const v = store.get("listenLevel");
  return v === "easy" || v === "hard" ? v : "medium";
}
/** Words in a verse are said when tapped, and their Listen buttons show (Easy, Medium). */
export const wordsSpeak = () => listenLevel() !== "hard";
/** A verse can be heard whole (Medium, Hard). */
export const versesSpeak = () => listenLevel() !== "easy";

/** A Listen button for one word of a verse: none on Hard. */
export function wordSayButton(text, lang, options) {
  return wordsSpeak() ? sayButton(text, lang, options) : "";
}

/** A Listen button for a whole verse: none on Easy. options.label defaults to "Listen to the verse". */
export function verseSayButton(text, lang, options) {
  const o = options || {};
  return versesSpeak() ? sayButton(text, lang, { label: "Listen to the verse", ...o }) : "";
}

/** A word of a verse was tapped: say it at once (Easy and Medium). */
const tapHelpShown = { grc: false, he: false };
export function sayTapped(text, lang) {
  if (!wordsSpeak() || !text) return;
  const l = lang === "he" ? "he" : "grc";
  // with no voice, explain once per language, not on every word tapped
  sayText(text, l, null, tapHelpShown[l]);
  tapHelpShown[l] = true;
}

/**
 * The grammar a Hebrew word's code shows, for the voice (sound.hebrewByGrammar): verb stem, form and person; the
 * article; the ה of direction; how many one-letter prefixes come first. code: STEPBible's, e.g. "HC/R/Ncmsc/Sp3ms",
 * "HVqp3cp", "HTd/Ncmsa".
 */
export function heGrammar(code) {
  const parts = String(code || "").replace(/^[HA]/, "").split("/");
  // conjunction (C, or c before a wayyiqtol), preposition, article, interrogative הֲ, relative שֶׁ: one letter each
  const main = parts.findIndex((x) => !/^(C|c|R|Rd|Td|Ti|Tr)$/.test(x));
  const v = parts.map((x) => x.match(/^V(\w)(\w)(\d)?([mfbc]?[spd]?)/)).find(Boolean);
  return {
    stem: v ? v[1] : "", form: v ? v[2] : "", person: v && v[3] ? v[3] : "", gn: v && v[4] ? v[4] : "", // gn: "fp", "ms"…
    article: parts.some((x) => x === "Td" || x === "Rd"),
    directional: parts.includes("Sd"),
    suffix: parts.some((x) => /^Sp/.test(x)), // a pronoun ending (יִשְׁמׇרְךָ)
    prefix: main > 0 ? main : 0,
  };
}

/**
 * A Hebrew word from the Bible data as the voice gets it: what its grammar and dictionary form settle (qamets or qamets
 * hatuf, a said or silent shewa, the stress at the verse's end). text: as written (default heText(w)); joined: a maqqef
 * follows; lex: the book's dictionary entries ({key: [lemma, …]}), when to hand.
 */
export function heVoice(w, text, joined, lex) {
  const t = text != null ? text : heText(w);
  if (!w) return t;
  const g = heGrammar(w[4]);
  g.joined = !!joined;
  g.final = /\u05C3/.test(String(w[5] || ""));
  const entry = typeof lex === "string" ? [lex] : lex && lex[heMainKey(w)];
  if (entry) g.lemma = String(entry[0] || "").split(",")[0];
  return hebrewByGrammar(t, g);
}

/**
 * What the voice reads for a whole verse, from the Bible data's words: Greek with its punctuation, so the voice pauses
 * where the text does; Hebrew with its maqqef, leaving out the words written but not read aloud (grey in the Reader).
 */
export function verseSpeech(words, lang, lex) {
  if (lang === "he") {
    // the maqqef keeps joined words together; sof pasuq ׃ ends the verse (the voice hears a full stop)
    return (words || []).filter((w) => w[6] !== "k").map((w) => heVoice(w, null, heJoined(w[5]), lex) + (heJoined(w[5]) ? "־" : /׃/.test(w[5] || "") ? "׃" : "")).join(" ").replace(/־ /g, "־");
  }
  return (words || []).map((w) => w[0] + String(w[5] || "").replace(/[¶¬]/g, "")).join(" ");
}

/**
 * The Septuagint (Swete) prints a book's first word or two in capitals without accents or breathings (ΕΝ ΑΡΧΗ,
 * ΟΡΑΣΙΣ, Ο ΔΕ). Shown as printed; said as the word it is, so the voice gets the stress and the rough breathing
 * (Erasmian h): keyed by the bare capitals. tools/check_pronunciation.mjs fails on any capitals not listed here.
 */
export const LXX_CAPS = {
  ΑΔΑΜ: "Ἀδάμ", ΚΑΙ: "καὶ", ΤΟΙΣ: "τοῖς", Ο: "ὁ", ΔΕ: "δὲ", ΦΙΛΟΣΟΦΩΤΑΤΟΝ: "φιλοσοφώτατον", ΛΟΓΟΙ: "λόγοι",
  ΕΠΙ: "ἐπὶ", ΕΝ: "ἐν", ΟΥΤΟΙ: "οὗτοι", ΡΗΜΑΤΑ: "ῥήματα", ΛΟΓΟΣ: "λόγος", ΕΤΟΥΣ: "ἔτους", ΤΑΥΤΑ: "ταῦτα",
  ΑΡΧΗ: "ἀρχῇ", ΤΟ: "τὸ", ΟΡΑΣΙΣ: "ὅρασις", ΑΝΘΡΩΠΟΣ: "ἄνθρωπος", ΑΝΤΙΓΡΑΦΟΝ: "ἀντίγραφον", ΛΗΜΜΑ: "λῆμμα",
  ΑΣΩΜΕΝ: "ᾄσωμεν", ΠΑΡΟΙΜΙΑΙ: "παροιμίαι", ΜΑΚΑΡΙΟΣ: "μακάριος", ΕΒΟΗΣΑ: "ἐβόησα", ΠΟΛΛΩΝ: "πολλῶν",
  ΠΑΣΑ: "πᾶσα", ΑΣΜΑ: "ᾆσμα", ΒΙΒΛΟΣ: "βίβλος", ΑΓΑΠΗΣΑΤΕ: "ἀγαπήσατε",
};
/** A word written in capitals only (two letters or more, or Ο), as its bare capitals; else "". */
export const lxxCapsKey = (word) => {
  const bare = String(word || "").normalize("NFD").replace(/[\u0300-\u036f\u1fbd\u2019]/g, "").normalize("NFC");
  return /^[Α-Ω]+$/.test(bare) && (bare.length > 1 || bare === "Ο") ? bare : "";
};
/**
 * Swete writes some numbers as letters with a mark (ιβ᾽ 12, ρ᾽ 100, βυ᾽ 2,400), the same mark as an elided word.
 * Said as the number words, in the form the sentence needs (NUM 29:13 ἀμνοὺς … ιδ᾽ → δεκατέσσαρας; JDG 20:24 τῇ
 * ἡμέρᾳ τῇ β᾽ → δευτέρᾳ). Keyed by the bare token; LXX_NUMBER_CONTEXT ("previous|token|next") for the few whose
 * form depends on the words around them. Every one of the 59 in the text was read in its verse (19 Nov 2026); the
 * pronunciation check fails on any numeral not listed. EZR 2:58 τοβ᾽ is said as printed (372; the Hebrew has 392).
 */
export const LXX_NUMBERS = {
  "β᾽": "δύο", "γ᾽": "τρεῖς", "ε᾽": "πέντε", "ζ᾽": "ἑπτά", "η᾽": "ὀκτώ", "ι᾽": "δέκα", "ια᾽": "ἕνδεκα", "ιβ᾽": "δώδεκα",
  "ιγ᾽": "δεκατρεῖς", "ιδ᾽": "δεκατέσσαρας", "κ᾽": "εἴκοσι", "κθ᾽": "εἴκοσι ἐννέα", "μ᾽": "τεσσεράκοντα", "ν᾽": "πεντήκοντα",
  "ξβ᾽": "ἑξήκοντα δύο", "ρ᾽": "ἑκατόν", "σν᾽": "διακοσίους πεντήκοντα", "φ᾽": "πεντακόσιοι", "χ᾽": "ἑξακόσιοι",
  "τοβ᾽": "τριακόσιοι ἑβδομήκοντα δύο", "ας᾽": "χίλιοι διακόσιοι", "βυ᾽": "δισχίλιαι τετρακόσιαι",
};
/** Their values, for the word sheet (ας᾽ is 1,200 and βυ᾽ 2,400: a thousands letter, then hundreds). */
export const LXX_NUMBER_VALUES = { "β᾽": 2, "γ᾽": 3, "ε᾽": 5, "ζ᾽": 7, "η᾽": 8, "ι᾽": 10, "ια᾽": 11, "ιβ᾽": 12, "ιγ᾽": 13, "ιδ᾽": 14,
  "κ᾽": 20, "κθ᾽": 29, "μ᾽": 40, "ν᾽": 50, "ξβ᾽": 62, "ρ᾽": 100, "σν᾽": 250, "φ᾽": 500, "χ᾽": 600, "τοβ᾽": 372, "ας᾽": 1200, "βυ᾽": 2400 };
export const LXX_NUMBER_CONTEXT = {
  "τῇ|β᾽|": "δευτέρᾳ", // JDG 20:24, 20:25 ἐν τῇ ἡμέρᾳ τῇ β᾽ (the second day; the verse ends there)
  "τὸ|ζ᾽|καὶ": "ἕβδομον", // NEH 10:31 τὸ ἔτος τὸ ζ᾽ (the seventh year)
  "τὴν|ε᾽|καὶ": "πέμπτην", "καὶ|ι᾽|τοῦ": "δεκάτην", // ESG 9:19 τὴν ε᾽ καὶ ι᾽ τοῦ Ἀδάρ (the fifteenth of Adar)
  "εἰς|χ᾽|ἄυδρας": "ἑξακοσίους", // JDG 3:31 εἰς χ᾽ ἄυδρας (six hundred men, after εἰς)
};
const bareToken = (tok) => String(tok || "").replace(/[.,;:·()\[\]]/g, "").replace(/’/g, "᾽").trim();
/** Is this token one of Swete's letter numerals (letters only, no accent or breathing, then the mark)? */
export const lxxIsNumeral = (tok) => /^[α-ωϛϙϡς]{1,4}᾽$/.test(bareToken(tok)) && !/^(μετ|μεθ|κατ|καθ|παρ|δι|δ|τ|ποτ|γ|μηδ)᾽$/.test(bareToken(tok)) || !!LXX_NUMBERS[bareToken(tok)];
/** The number words for a numeral token between prev and next (tokens as written), or "" if it isn't one. */
export function lxxNumber(tok, prev, next) {
  const t = bareToken(tok);
  if (!LXX_NUMBERS[t] && !lxxIsNumeral(t)) return "";
  const key = `${bareToken(prev)}|${t}|${bareToken(next)}`;
  return LXX_NUMBER_CONTEXT[key] || LXX_NUMBERS[t] || "";
}
/** One word as the voice gets it: capitals said as the word they are, numerals as number words. */
function lxxSayToken(tok, prev, next) {
  const n = lxxNumber(tok, prev, next);
  if (n) { const p = String(tok).match(/[.,;:·)\]]+$/); return n + (p ? p[0].replace(/[)\]]/g, "") : ""); }
  const m = String(tok).match(/^([^\u0370-\u03FF\u1F00-\u1FFF]*)(.*?)([^\u0370-\u03FF\u1F00-\u1FFF]*)$/);
  const k = m && lxxCapsKey(m[2]);
  return k && LXX_CAPS[k] ? m[1] + LXX_CAPS[k] + m[3] : tok;
}
/**
 * A Septuagint verse's words as the Reader shows them and the voice reads them. The digital Swete sometimes puts a
 * space before a mark (ἀνομίᾳ , καὶ) or none after one (Ὠμάρ,Σωφάρ; ὀπίσω;διότι): the mark joins its word and a space
 * follows it, so no mark stands alone as a "word" and no two words run together (the Erasmian voice once said
 * Ὠμάρ,Σωφάρ as one word).
 */
export const lxxTokens = (text) => String(text || "").replace(/\s+([,.;·])/g, "$1")
  .replace(/([,.;·])(?=[\u0370-\u03FF\u1F00-\u1FFF])/g, "$1 ").split(" ").filter(Boolean);
/** The strongest of a run of marks (αὐτοί·. → .), so the voice pauses once. */
const oneMark = (run) => (/;/.test(run) ? ";" : /\./.test(run) ? "." : /·/.test(run) ? "·" : ",");
/** A Septuagint verse as the voice gets it. */
export const lxxSpeech = (text) => {
  const toks = lxxTokens(text);
  return toks.map((tok, i) => lxxSayToken(tok, toks[i - 1], toks[i + 1]).replace(/[,.;·]{2,}$/, oneMark)).join(" ");
};
/**
 * A tapped Septuagint word (with the words either side of it): what the sheet shows (punctuation off, an elision
 * mark kept: δ᾽), what the dictionary looks up (without the mark) and what the voice says (the voice restores an
 * elided vowel: δ᾽ is de, not the letter delta; a numeral is its number words).
 */
export function lxxTapWord(token, prev, next) {
  const show = String(token || "").replace(/[.,;:·()\[\]]/g, "").trim();
  const number = lxxNumber(show, prev, next);
  return { show, look: number ? number.split(" ")[0] : show.replace(/[᾽’]/g, ""), say: lxxSayToken(show, prev, next), number, value: number ? LXX_NUMBER_VALUES[bareToken(show)] : 0 };
}

/** One handler for every listen button (they can sit inside links and rows: the click stays with the button). */
export function bindAudio(root) {
  (root || document).addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest("[data-say]");
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    play(b);
  }, true);
  window.addEventListener("hashchange", () => stopSpeaking());
  warmUpVoices();
}

export { canSpeak };
