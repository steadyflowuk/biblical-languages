// Listen buttons (Session 9): <button data-say="λόγος" data-say-lang="grc">. One click handler for the whole app
// (bound in app.js), so any screen can drop in sayButton() without wiring. Speech itself lives in sound.js.
import * as store from "./store.js";
import { speak, speechText, canSpeak, stopSpeaking, warmUpVoices } from "./sound.js";

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const ICON = `<svg class="say-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path class="say-wave" d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>`;

/**
 * A listen button. text: the Greek or Hebrew to say; lang: "grc" | "he".
 * options.label: visible words next to the icon (default none: icon only, named for screen readers).
 */
export function sayButton(text, lang, options) {
  const o = options || {};
  // nothing a voice could say (a lone paragraph mark, a dash): no button
  if (!text || !/[\u05D0-\u05EA\u0370-\u03FF\u1F00-\u1FFF]/.test(speechText(text, lang === "he" ? "he" : "grc"))) return "";
  const name = o.label || "Listen";
  return `<button type="button" class="say-btn${o.label ? " with-label" : ""}${o.className ? " " + o.className : ""}" data-say="${esc(text)}" data-say-lang="${lang === "he" ? "he" : "grc"}" aria-label="${esc(o.label ? name : `${name}: ${text}`)}">${ICON}${o.label ? `<span>${esc(o.label)}</span>` : ""}</button>`;
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
  if (playing) playing.classList.remove("playing");
  playing = button;
  button.classList.add("playing");
  const lang = button.dataset.sayLang;
  const done = () => { button.classList.remove("playing"); if (playing === button) playing = null; };
  // no waiting before speak(): phones only allow speech that starts inside the tap
  const r = speak(button.dataset.say, {
    lang, greekVoice: store.get("greekVoice"), rate: store.get("speechRate"), onend: done,
    onfail: () => { done(); notice(voiceHelp(lang)); },
  });
  if (!r.ok) {
    done();
    notice(r.why === "no-voice" ? voiceHelp(lang) : "This browser can't speak words aloud. Try the app in Safari on an iPhone or iPad, or Chrome on Android.");
  }
  return r;
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
