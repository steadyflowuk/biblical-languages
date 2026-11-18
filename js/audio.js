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
  const v = parts.map((x) => x.match(/^V(\w)(\w)(\d)?/)).find(Boolean);
  return {
    stem: v ? v[1] : "", form: v ? v[2] : "", person: v && v[3] ? v[3] : "",
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
