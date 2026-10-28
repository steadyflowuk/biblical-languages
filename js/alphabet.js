// Alphabet and sounds (route #/alphabet/grc | #/alphabet/he): every letter, the marks and letter pairs that change a
// sound, Erasmian beside Restored Koine (Greek), signs in the Bible text, and verses to read aloud.
// Content: lessons/alphabet/<lang>.json (checked by tools/check_lessons.py like the lessons).
import * as store from "./store.js";
import * as data from "./data.js";
import { head } from "./screens.js";
import { mixed, tableHTML } from "./lessons.js";
import { openSheet } from "./reader.js";
import { sayButton } from "./audio.js";
import { greekSay } from "./sound.js";
import { heText, heAfter, heJoined } from "./hebrew.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const NAME = { grc: "Greek", he: "Hebrew" };
const cache = {};
const guide = (lang) => {
  if (!cache[lang]) cache[lang] = data.getJSON(`lessons/alphabet/${lang}.json`).catch((e) => { delete cache[lang]; throw e; });
  return cache[lang];
};
export { guide as alphabetGuide };

const textAttrs = (lang) => (lang === "he" ? ' lang="he" dir="rtl"' : ' lang="grc"');

function exampleHTML(ex, lang) {
  return `<li>
    <span class="ls-ex-head"><span class="ls-ex-t"${textAttrs(lang)}>${esc(ex.t)}</span>${sayButton(ex.t, lang, { className: "small" })}</span>
    <span class="ls-ex-say">${esc(ex.say)}</span>
    <span class="ls-ex-en">${mixed(ex.en)}</span></li>`;
}

function tileHTML(L, i, lang) {
  return `<li><button type="button" class="ab-tile" data-letter="${i}" aria-label="${esc(L.name)}: ${esc(L.sound)}">
    <span class="ab-glyph"${textAttrs(lang)}>${L.forms.map(esc).join(" ")}</span>
    <span class="ab-name">${esc(L.name)}</span>
    <span class="ab-sound">${esc(shortSound(L.sound))}</span></button></li>`;
}
const shortSound = (s) => String(s).split(/[;(]/)[0].replace(/ as in .*/, "").trim();

function letterSheetHTML(L, i, A, lang) {
  const koine = lang === "grc" && L.koine;
  const voice = store.get("greekVoice") === "koine" ? "koine" : "erasmian";
  return `<p class="ws-ref">${NAME[lang]} letter ${i + 1} of ${A.letters.length}</p>
    <h2 class="ab-big" id="sheet-title"${textAttrs(lang)}>${L.forms.map(esc).join(" ")}</h2>
    <p class="ab-sheet-name"><strong>${esc(L.name)}</strong> <span${textAttrs(lang)}>${esc(L.nameT)}</span> <span class="muted">${esc(L.nameSay)}</span>
      ${sayButton(L.nameT, lang, { className: "small" })}</p>
    <dl class="ws-facts">
      <div><dt>${lang === "grc" ? "Sound (Erasmian)" : "Sound"}</dt><dd>${mixed(L.sound)}${lang === "grc" && voice === "erasmian" ? ` <span class="tag">used in the app</span>` : ""}</dd></div>
      ${koine ? `<div><dt>Restored Koine</dt><dd>${mixed(L.koine)}${voice === "koine" ? ` <span class="tag">used in the app</span>` : ""}</dd></div>` : ""}
      ${L.tip ? `<div><dt>Look out</dt><dd>${mixed(L.tip)}</dd></div>` : ""}
    </dl>
    <h3 class="ab-sub">${L.example2 ? "Examples" : "Example"}</h3>
    <ul class="ls-examples">${[L.example, L.example2].filter(Boolean).map((ex) => exampleHTML(ex, lang)).join("")}</ul>
    <div class="btn-row ab-steps">
      <button type="button" class="btn secondary" data-step="-1"${i === 0 ? " disabled" : ""}>‹ ${i === 0 ? "Previous" : esc(A.letters[i - 1].name)}</button>
      <button type="button" class="btn secondary" data-step="1"${i === A.letters.length - 1 ? " disabled" : ""}>${i === A.letters.length - 1 ? "Next" : esc(A.letters[i + 1].name)} ›</button>
    </div>`;
}

function sectionHTML(sec, lang) {
  return `<section class="ab-section">
    <h2>${mixed(sec.title)}</h2>
    ${(sec.body || []).map((p) => `<p>${mixed(p)}</p>`).join("")}
    ${sec.table ? tableHTML(sec.table) : ""}
    ${sec.examples && sec.examples.length ? `<ul class="ls-examples">${sec.examples.map((ex) => exampleHTML(ex, lang)).join("")}</ul>` : ""}
  </section>`;
}

/** A verse's text as printed (Greek with its punctuation; Hebrew with maqqef and sof pasuq). */
function verseText(words, lang) {
  if (lang === "grc") return words.map((w) => w[0] + String(w[5] || "").replace(/[¶¬]/g, "")).join(" ");
  return words.map((w) => heText(w) + (heJoined(w[5]) ? "־" : heAfter(w[5]) ? heAfter(w[5]) : "")).join(" ").replace(/־ /g, "־");
}

async function practiceHTML(A, lang) {
  const out = await Promise.all((A.practice || []).map(async (pr) => {
    const [book, cv] = pr.ref.split(" ");
    const [ch, v] = cv.split(":").map(Number);
    let text = "";
    try {
      const book_ = await data.original(book);
      const words = ((book_.ch.find(([c]) => c === ch) || [0, []])[1].find(([n]) => n === v) || [0, []])[1];
      text = verseText(words, lang).replace(/[֑-ֽ֯]/g, "");
    } catch (e) { /* offline: show the rest */ }
    const books = await data.books().catch(() => []);
    const b = books.find((x) => x.id === book);
    const name = `${b ? (b.id === "PSA" ? "Psalm" : b.name) : book} ${ch}:${v}`;
    const say = lang === "grc" ? greekSay(text) : pr.say;
    return `<li class="ab-verse">
      <p class="ab-verse-ref"><a href="#/read/${book}/${ch}/${v}">${esc(name)}</a></p>
      ${text ? `<p class="ab-verse-t"${textAttrs(lang)}>${esc(text)}</p>` : `<p class="muted">The verse needs a connection the first time.</p>`}
      <p class="ls-ex-say">${esc(say)}</p>
      <p class="ab-verse-en">${esc(pr.en)}</p>
      ${text ? `<p>${sayButton(text, lang, { label: "Listen" })}</p>` : ""}
    </li>`;
  }));
  return out.join("");
}

export const alphabet = {
  title: "Alphabet and sounds",
  async render(main, params) {
    const want = params[0] || store.get("abcLang") || store.get("learnLang");
    const lang = want === "he" ? "he" : "grc";
    if (params[0]) store.set("abcLang", lang);
    main.innerHTML = `<div class="screen ab">${head("Alphabet and sounds", `${NAME[lang]}: letters, marks and how to say them`)}<p class="muted">Loading…</p></div>`;
    let A;
    try {
      A = await guide(lang);
    } catch (e) {
      main.innerHTML = `<div class="screen ab">${head("Alphabet and sounds", "")}<div class="note"><p>The guide couldn't load. Check your connection and try again.</p>
        <p><button type="button" class="btn" data-retry>Try again</button></p></div></div>`;
      main.querySelector("[data-retry]").addEventListener("click", () => this.render(main, params));
      return;
    }
    if (location.hash.indexOf("#/alphabet") !== 0) return;
    const decks = store.get("reviewDecks") || {};
    main.innerHTML = `<div class="screen ab">
      ${head("Alphabet and sounds", `${NAME[lang]}: letters, marks and how to say them`)}
      <div class="switch" role="group" aria-label="Language">
        <a class="switch-link" href="#/alphabet/grc" aria-current="${lang === "grc" ? "page" : "false"}">Greek</a>
        <a class="switch-link" href="#/alphabet/he" aria-current="${lang === "he" ? "page" : "false"}">Hebrew</a>
      </div>
      <p>${mixed(A.intro)}</p>
      ${lang === "grc" ? `<p class="muted ab-tip">Capital and small forms side by side; the Bible text is mostly small letters.</p>` : ""}
      <h2>The ${A.letters.length} letters</h2>
      <ul class="ab-grid"${lang === "he" ? ' dir="rtl"' : ""}>${A.letters.map((L, i) => tileHTML(L, i, lang)).join("")}</ul>
      ${A.sections.map((sec) => sectionHTML(sec, lang)).join("")}
      <section class="ab-section">
        <h2>Read aloud</h2>
        <p>Real verses, with the pronunciation written out. Listen, then read along.</p>
        <ul class="ab-verses"><li class="muted">Loading the verses…</li></ul>
      </section>
      <div class="note ab-practise">
        <p>${decks[lang + "Letters"] ? "The letters are in your review list." : "Practise the letters with flashcards: switch on the alphabet in Review."}</p>
        <p class="btn-row"><a class="btn secondary" href="#/review">Go to Review</a> <a class="btn secondary" href="#/learn">Back to Learn</a></p>
      </div>
    </div>`;
    practiceHTML(A, lang).then((html) => {
      const ul = main.querySelector(".ab-verses");
      if (ul) ul.innerHTML = html;
    });
    const show = (i, from) => {
      const body = openSheet(letterSheetHTML(A.letters[i], i, A, lang), { label: `${A.letters[i].name}`, returnFocus: from });
      body.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
        const j = i + Number(b.dataset.step);
        if (j >= 0 && j < A.letters.length) show(j, main.querySelector(`[data-letter="${j}"]`));
      }));
    };
    main.querySelectorAll("[data-letter]").forEach((b) => b.addEventListener("click", () => show(Number(b.dataset.letter), b)));
  },
};
