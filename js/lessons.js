// Lessons: the five-step loop (hear and see → notice → practise → read → review), drills and progress.
// A lesson is a JSON file in lessons/<lang>/ (format: lessons/README.md); this file turns it into screens.
// Progress lives in store "lessons" (id → { pos, retries, first, done, best, completed }); the words of finished
// lessons go to store "reviewQueue" for the review trainer.

import * as store from "./store.js";
import * as data from "./data.js";
import { friendlyGrammar, bsbChapter, englishHTML } from "./reader.js";
import { heText, heEnglish, heAfter, heJoined, heMainKey, heParts, heFriendlyGrammar } from "./hebrew.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export const STEP_NAMES = { hear: "Hear and see", notice: "Notice", practise: "Practise", read: "Read", review: "Review" };
const STEP_SHORT = { hear: "Hear" };
const STEP_ORDER = ["hear", "notice", "practise", "read", "review"];
const DRILLS = new Set(["choose", "match", "build", "parse"]);
const LANG_NAME = { grc: "Greek", he: "Hebrew" };

const GREEK_RUN = /[Ͱ-Ͽἀ-῿][Ͱ-Ͽἀ-῿̀-ͯ\s,.;·’᾽]*[Ͱ-Ͽἀ-῿̀-ͯ]|[Ͱ-Ͽἀ-῿]/g;
const HEBREW_RUN = /[א-ת][֑-ׇא-ת\s־]*[֑-ׇא-ת]|[א-ת]/g;
const isHebrew = (s) => /[א-ת]/.test(String(s));
const isGreek = (s) => /[Ͱ-Ͽἀ-῿]/.test(String(s));

/** Escape text, marking runs of Greek or Hebrew so they get the right font and direction inside English. */
export function mixed(text) {
  return esc(text)
    .replace(HEBREW_RUN, (m) => `<bdi lang="he" class="t-he">${m}</bdi>`)
    .replace(GREEK_RUN, (m) => `<span lang="grc" class="t-grc">${m}</span>`);
}
/** Attributes for a piece of text that is wholly in one script. */
const langAttrs = (s) => (isHebrew(s) ? ' lang="he" dir="rtl"' : isGreek(s) ? ' lang="grc"' : "");

function shuffled(list) {
  const a = list.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const t = a[i]; a[i] = a[j]; a[j] = t;
  }
  return a;
}
/** Shuffle, but never leave the items in their original order (that would give the answer away). */
function mixedUp(list) {
  if (list.length < 2) return list.slice();
  let a = shuffled(list);
  for (let n = 0; n < 6 && a.every((x, i) => x === list[i]); n++) a = shuffled(list);
  if (a.every((x, i) => x === list[i])) a = list.slice(1).concat(list[0]);
  return a;
}

// ---------------------------------------------------------------- loading and progress

export const lessonIndex = () => data.getJSON("lessons/index.json");
const loadLesson = (file) => data.getJSON(file);

export function progressOf(id) {
  return (store.get("lessons") || {})[id] || null;
}
function saveProgress(id, p) {
  const all = Object.assign({}, store.get("lessons") || {});
  all[id] = p;
  store.set("lessons", all);
}

/** The lesson to do next in a language: the first written lesson not yet finished (or null when all are done). */
export function nextLesson(index, lang) {
  return (index[lang] || []).find((e) => e.file && !(progressOf(e.id) || {}).done) || null;
}

/** Words collected from finished lessons (the review list). */
export const reviewWords = () => store.get("reviewQueue") || [];

/** Lexicon keys the learner has met: their review words, plus a lesson's own words while doing it. */
function knownNumbers(extra) {
  const num = (k) => String(k || "").replace(/^([GH])0*(\d+).*$/, "$1$2");
  return new Set(reviewWords().map((w) => num(w.k)).concat((extra || []).map(num)));
}
const keyNumber = (k) => String(k || "").replace(/^([GH])0*(\d+).*$/, "$1$2");

// ---------------------------------------------------------------- the sequence of cards

/** Cards in order: hear + notice + practise, then any drills to try again, then read + review. */
function sequence(lesson, retries) {
  const out = [];
  lesson.steps.forEach((s) => {
    s.cards.forEach((c, i) => out.push({ step: s.step, card: c, base: `${s.step}.${i}`, first: i === 0, intro: i === 0 ? s.intro : "" }));
    if (s.step === "practise") {
      (retries || []).forEach((b) => {
        const [, i] = b.split(".");
        out.push({ step: "practise", card: s.cards[+i], base: b, retry: true });
      });
    }
  });
  return out;
}

// ---------------------------------------------------------------- card views

function stepBar(step) {
  const at = STEP_ORDER.indexOf(step);
  return `<ol class="ls-steps" aria-label="Steps">${STEP_ORDER.map((s, i) =>
    `<li class="${i < at ? "done" : i === at ? "now" : ""}" ${i === at ? 'aria-current="step"' : ""}><span class="ls-step-full">${STEP_NAMES[s]}</span>${STEP_SHORT[s] ? `<span class="ls-step-short" aria-hidden="true">${STEP_SHORT[s]}</span>` : ""}</li>`).join("")}</ol>`;
}

function sceneHTML(c) {
  return `<div class="ls-scene">
      <div class="ls-picture" aria-hidden="true">${esc(c.picture || "")}</div>
      <p class="ls-big"${langAttrs(c.text)}>${esc(c.text)}</p>
      <p class="ls-say"><span class="sr">Say it: </span>${esc(c.say)}</p>
      <div class="ls-reveal">
        <button type="button" class="btn secondary" data-reveal aria-expanded="false">Show the English</button>
        <p class="ls-en" hidden>${mixed(c.en)}</p>
      </div>
    </div>`;
}

function videoHTML(c) {
  return `<div class="ls-video">
      <h2 class="ls-title" tabindex="-1">${mixed(c.title)}</h2>
      ${c.note ? `<p>${mixed(c.note)}</p>` : ""}
      <p><a class="btn secondary" href="${esc(c.href)}" target="_blank" rel="noopener">Watch the video <span aria-hidden="true">↗</span></a></p>
    </div>`;
}

function explainHTML(c) {
  return `<div class="ls-explain">
      <h2 class="ls-title" tabindex="-1">${mixed(c.title)}</h2>
      ${(c.body || []).map((p) => `<p>${mixed(p)}</p>`).join("")}
      ${c.examples && c.examples.length ? `<ul class="ls-examples">${c.examples.map((x) => `<li>
        <span class="ls-ex-t"${langAttrs(x.t)}>${esc(x.t)}</span>
        ${x.say ? `<span class="ls-ex-say">${esc(x.say)}</span>` : ""}
        <span class="ls-ex-en">${mixed(x.en)}</span></li>`).join("")}</ul>` : ""}
    </div>`;
}

function chooseHTML(c, state) {
  state.order = state.order || mixedUp(c.options.map((_, i) => i));
  return `<div class="ls-drill ls-choose">
      <h2 class="ls-title" tabindex="-1">${mixed(c.prompt)}</h2>
      <div class="ls-options" role="group" aria-label="Answers">${state.order.map((i) =>
        `<button type="button" class="ls-option" data-opt="${i}"${langAttrs(c.options[i])}>${esc(c.options[i])}</button>`).join("")}</div>
    </div>`;
}

function matchHTML(c, state) {
  state.left = state.left || mixedUp(c.pairs.map((_, i) => i));
  state.right = state.right || mixedUp(c.pairs.map((_, i) => i));
  return `<div class="ls-drill ls-match">
      <h2 class="ls-title" tabindex="-1">${mixed(c.prompt || "Match the pairs.")}</h2>
      <p class="muted ls-how">Tap a word, then its meaning.</p>
      <div class="ls-match-cols">
        <div class="ls-col" role="group" aria-label="Words">${state.left.map((i) =>
          `<button type="button" class="ls-tile" data-left="${i}"${langAttrs(c.pairs[i][0])} aria-pressed="false">${esc(c.pairs[i][0])}</button>`).join("")}</div>
        <div class="ls-col" role="group" aria-label="Meanings">${state.right.map((i) =>
          `<button type="button" class="ls-tile" data-right="${i}"${langAttrs(c.pairs[i][1])}>${esc(c.pairs[i][1])}</button>`).join("")}</div>
      </div>
    </div>`;
}

function buildHTML(c, state, lang) {
  state.bank = state.bank || mixedUp(c.tiles.map((_, i) => i));
  state.line = state.line || [];
  const dir = lang === "he" ? ' dir="rtl"' : "";
  const tile = (i, where) => `<button type="button" class="ls-tile" data-${where}="${i}"${langAttrs(c.tiles[i])}>${esc(c.tiles[i])}</button>`;
  return `<div class="ls-drill ls-build">
      <h2 class="ls-title" tabindex="-1">${mixed(c.prompt)}</h2>
      <p class="muted ls-how">Tap the words in order. Tap a placed word to take it back.</p>
      <div class="ls-line"${dir} aria-label="Your answer" role="group">${state.line.length ? state.line.map((i) => tile(i, "placed")).join("") : `<span class="ls-line-empty">Your answer</span>`}</div>
      <div class="ls-bank"${dir} role="group" aria-label="Words to use">${state.bank.filter((i) => !state.line.includes(i)).map((i) => tile(i, "tile")).join("")}</div>
      <p><button type="button" class="btn" data-check ${state.line.length === c.tiles.length ? "" : "disabled"}>Check</button></p>
    </div>`;
}

function parseHTML(c, state) {
  state.picks = state.picks || {};
  return `<div class="ls-drill ls-parse">
      <h2 class="ls-title" tabindex="-1">${mixed(c.prompt || "Describe this word.")}</h2>
      <p class="ls-big"${langAttrs(c.word)}>${esc(c.word)}</p>
      ${c.fields.map((f, fi) => `<fieldset class="ls-field" data-field="${fi}">
        <legend>${mixed(f.label)}</legend>
        <div class="ls-chips">${f.options.map((o) =>
          `<button type="button" class="ls-chip" data-pick="${fi}" data-value="${esc(o)}" aria-pressed="${state.picks[fi] === o}">${mixed(o)}</button>`).join("")}</div>
      </fieldset>`).join("")}
      <p><button type="button" class="btn" data-check ${Object.keys(state.picks).length === c.fields.length ? "" : "disabled"}>Check</button></p>
    </div>`;
}

function wordsHTML(c) {
  return `<div class="ls-words">
      <h2 class="ls-title" tabindex="-1">Words from this lesson</h2>
      <p>These ${c.items.length} words go into your review list when you finish, so you see them again before you forget them.</p>
      <ul class="ls-wordlist">${c.items.map((w) => `<li>
        <a class="ls-word-t" href="#/words/${encodeURIComponent(w.k)}"${langAttrs(w.t)}>${esc(w.t)}</a>
        <span class="ls-ex-say">${esc(w.say)}</span>
        <span class="ls-ex-en">${mixed(w.en)}</span></li>`).join("")}</ul>
    </div>`;
}

// ---------------------------------------------------------------- reading a real verse

async function verseView(card, lang, known) {
  const [bookId, cv] = card.ref.split(" ");
  const [ch, v] = cv.split(":").map(Number);
  const [books, original, morph, bsbBook] = await Promise.all([data.books(), data.original(bookId), data.morph(lang), data.bsb(bookId)]);
  const book = books.find((b) => b.id === bookId);
  const words = ((original.ch.find(([c]) => c === ch) || [0, []])[1].find(([n]) => n === v) || [0, []])[1];
  const english = bsbChapter(bsbBook, ch).verses.get(v) || "";
  const he = lang === "he";
  const name = `${book.id === "PSA" ? "Psalm" : book.name} ${ch}:${v}`;
  let knownCount = 0;
  const html = words.map((w, i) => {
    const key = he ? heMainKey(w) : w[3];
    const isKnown = known.has(keyNumber(key));
    if (isKnown) knownCount++;
    const text = he ? heText(w) : w[0];
    const en = englishHTML(he ? heEnglish(w[2]) : w[2]); // safe HTML: "<the>" greyed, "[the]" in italics, as in the Reader
    const after = he ? heAfter(w[5]) : String(w[5] || "").replace(/[¶¬]/g, "");
    return `<button type="button" class="ls-vw${isKnown ? " known" : ""}" data-w="${i}"${he ? ' lang="he"' : ' lang="grc"'}>
      <span class="ls-vw-t">${esc(text)}${esc(after && !heJoined(after) ? after : he && heJoined(after) ? "־" : "")}</span>
      <span class="ls-vw-en" lang="en" dir="ltr">${en}</span></button>`;
  }).join("");
  const gloss = (i) => {
    const w = words[i];
    const key = he ? heMainKey(w) : w[3];
    const lex = original.lex[key] || [];
    const code = he ? (heParts(w).find((p) => p.main) || {}).code : w[4];
    const desc = (morph[code] || [code])[0];
    return `<p><span class="ls-gl-lemma"${he ? ' lang="he" dir="rtl"' : ' lang="grc"'}>${esc(lex[0] || (he ? heText(w) : w[0]))}</span>
      <span class="ls-gl-en">${esc(String(lex[2] || "").split(": ").pop())}</span></p>
      <p class="muted">${esc(he ? heFriendlyGrammar(desc) : friendlyGrammar(desc))}</p>
      ${key ? `<p><a class="verse-link" href="#/words/${encodeURIComponent(key)}">Look it up in the dictionary</a></p>` : ""}`;
  };
  return {
    html: `<div class="ls-verse">
      <h2 class="ls-title" tabindex="-1">${esc(name)}</h2>
      <p class="muted ls-known">You know ${knownCount} of these ${words.length} words.</p>
      <div class="ls-verse-words"${he ? ' dir="rtl"' : ""}>${html}</div>
      <div class="ls-gloss" aria-live="polite"></div>
      <p class="ls-verse-en">${esc(english.replace(/\u0001\d+\u0001/g, ""))} <span class="muted">(BSB)</span></p>
      ${card.note ? `<p class="ls-note">${mixed(card.note)}</p>` : ""}
      <p><a class="verse-link" href="#/read/${bookId}/${ch}/${v}">Open ${esc(name)} in the Reader</a></p>
    </div>`,
    gloss,
  };
}

// ---------------------------------------------------------------- the lesson screen (#/lesson/LANG/ID)

export const lesson = {
  title: "Lesson",
  handlesTitle: true,
  async render(main, params = []) {
    const [lang, id] = params;
    let index;
    try {
      index = await lessonIndex();
    } catch {
      main.innerHTML = `<div class="screen"><div class="note"><p>The lessons couldn't load. Check you're connected to the internet.</p>
        <p><button type="button" class="btn secondary" data-retry>Try again</button></p></div></div>`;
      main.querySelector("[data-retry]").addEventListener("click", () => this.render(main, params));
      return;
    }
    const entries = index[lang] || [];
    const entry = entries.find((e) => e.id === id && e.file);
    if (!entry) {
      main.innerHTML = `<div class="screen"><div class="note"><p>That lesson isn't ready yet.</p></div><p><a class="btn" href="#/learn">Back to Learn</a></p></div>`;
      document.title = "Lesson · Aleph to Omega";
      return;
    }
    let L;
    try {
      L = await loadLesson(entry.file);
    } catch {
      main.innerHTML = `<div class="screen"><div class="note"><p>This lesson couldn't load. Check you're connected to the internet; once opened, it works offline.</p>
        <p><button type="button" class="btn secondary" data-retry>Try again</button></p></div></div>`;
      main.querySelector("[data-retry]").addEventListener("click", () => this.render(main, params));
      return;
    }
    document.title = `${entry.title} · Aleph to Omega`;
    const lessonWords = [];
    L.steps.filter((s) => s.step === "review").forEach((s) => s.cards.forEach((c) => (c.items || []).forEach((w) => lessonWords.push(w.k))));

    // progress: start again if the lesson was finished, else carry on where it was left
    let p = progressOf(id);
    // the lesson's shape: if the file has changed since the learner's place was saved, start it again cleanly
    const sig = L.steps.map((s) => `${s.step}:${s.cards.length}`).join(",");
    if (!p || p.done || p.v !== 1 || p.sig !== sig) {
      p = { v: 1, sig, pos: 0, retries: [], first: {}, done: p && p.done, best: p && p.best, completed: p && p.completed };
    }
    let seq = sequence(L, p.retries);
    if (p.pos >= seq.length) p.pos = 0;
    let state = {}; // the current card's answers
    let answered = false;

    main.innerHTML = `<div class="screen lesson" lang="en">
      <header class="ls-head">
        <a class="icon-btn ls-close" href="#/learn" aria-label="Leave the lesson (your place is saved)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></a>
        <div class="ls-head-text"><p class="ls-kicker">${LANG_NAME[lang]} · ${esc(entry.title)}</p>
          <div class="ls-progress" role="progressbar" aria-label="Lesson progress" aria-valuemin="0" aria-valuemax="100"><span></span></div></div>
      </header>
      <div class="ls-stepbar"></div>
      <div class="ls-card"></div>
      <div class="ls-feedback" role="status" aria-live="polite"></div>
      <nav class="ls-nav">
        <button type="button" class="btn secondary" data-back>Back</button>
        <button type="button" class="btn" data-next>Continue</button>
      </nav>
    </div>`;
    window.scrollTo(0, 0);
    const box = main.querySelector(".ls-card");
    const feedback = main.querySelector(".ls-feedback");
    const nextBtn = main.querySelector("[data-next]");
    const backBtn = main.querySelector("[data-back]");
    let gloss = null;

    const isDrill = (item) => DRILLS.has(item.card.type);
    const setFeedback = (ok, text) => {
      feedback.className = `ls-feedback ${ok === true ? "good" : ok === false ? "try" : ""}`;
      feedback.innerHTML = text || "";
    };
    const answer = (ok, explain) => {
      const item = seq[p.pos];
      answered = true;
      if (!item.retry && p.first[item.base] === undefined) {
        p.first[item.base] = ok;
        if (!ok && !p.retries.includes(item.base)) {
          p.retries.push(item.base);
          seq = sequence(L, p.retries);
        }
      }
      setFeedback(ok, `<strong>${ok ? "Right." : "Not quite."}</strong> ${explain ? mixed(explain) : ""}${!ok && !item.retry ? ` <span class="muted">You'll get another go at this one before the end of the practice.</span>` : ""}`);
      nextBtn.disabled = false;
      nextBtn.focus({ preventScroll: true }); // keyboard and screen-reader users go straight on (the feedback is announced)
      saveProgress(id, p);
    };

    const draw = async () => {
      const item = seq[p.pos];
      const c = item.card;
      state = {};
      // a drill already answered (going Back, or reopening the lesson) doesn't have to be answered again
      answered = !isDrill(item) || (!item.retry && p.first[item.base] !== undefined);
      gloss = null;
      setFeedback(null, "");
      main.querySelector(".ls-stepbar").innerHTML = stepBar(item.step);
      const pct = Math.round((p.pos / seq.length) * 100);
      const bar = main.querySelector(".ls-progress");
      bar.setAttribute("aria-valuenow", String(pct));
      bar.querySelector("span").style.width = `${Math.max(3, pct)}%`;
      backBtn.hidden = p.pos === 0;
      nextBtn.disabled = !answered;
      nextBtn.textContent = p.pos === seq.length - 1 ? "Finish the lesson" : "Continue";
      const intro = item.intro ? `<p class="ls-intro">${mixed(item.intro)}</p>` : "";
      const again = item.retry ? `<p class="ls-again">Have another go</p>` : "";
      let html = "";
      if (c.type === "scene") html = sceneHTML(c);
      else if (c.type === "video") html = videoHTML(c);
      else if (c.type === "explain") html = explainHTML(c);
      else if (c.type === "choose") html = chooseHTML(c, state);
      else if (c.type === "match") html = matchHTML(c, state);
      else if (c.type === "build") html = buildHTML(c, state, lang);
      else if (c.type === "parse") html = parseHTML(c, state);
      else if (c.type === "words") html = wordsHTML(c);
      else if (c.type === "verse") {
        box.innerHTML = `${intro}<p class="muted">Loading the verse…</p>`;
        try {
          const view = await verseView(c, lang, knownNumbers(lessonWords));
          if (seq[p.pos] !== item) return; // moved on
          html = view.html;
          gloss = view.gloss;
        } catch {
          html = `<div class="note"><p>This verse couldn't load. Check you're connected to the internet; you can carry on without it.</p></div>`;
        }
      }
      box.innerHTML = intro + again + html;
      const title = box.querySelector(".ls-title, .ls-big");
      if (title && document.activeElement && document.activeElement !== document.body && main.contains(document.activeElement)) {
        if (!title.hasAttribute("tabindex")) title.setAttribute("tabindex", "-1");
        title.focus({ preventScroll: true });
      }
    };

    // ---- interaction on the current card
    box.addEventListener("click", (e) => {
      const item = seq[p.pos];
      const c = item.card;
      const reveal = e.target.closest("[data-reveal]");
      if (reveal) {
        const en = box.querySelector(".ls-en");
        en.hidden = !en.hidden;
        reveal.setAttribute("aria-expanded", String(!en.hidden));
        reveal.textContent = en.hidden ? "Show the English" : "Hide the English";
        return;
      }
      const vw = e.target.closest(".ls-vw");
      if (vw && gloss) {
        box.querySelectorAll(".ls-vw.on").forEach((x) => x.classList.remove("on"));
        vw.classList.add("on");
        box.querySelector(".ls-gloss").innerHTML = gloss(Number(vw.dataset.w));
        return;
      }
      if (c.type === "choose") {
        const b = e.target.closest("[data-opt]");
        if (!b || answered) return;
        const ok = Number(b.dataset.opt) === c.answer;
        box.querySelectorAll("[data-opt]").forEach((x) => {
          x.disabled = true;
          if (Number(x.dataset.opt) === c.answer) x.classList.add("right");
        });
        if (!ok) b.classList.add("wrong");
        answer(ok, c.explain);
      } else if (c.type === "match") {
        const left = e.target.closest("[data-left]");
        const right = e.target.closest("[data-right]");
        if (left && !left.disabled) {
          box.querySelectorAll("[data-left]").forEach((x) => x.setAttribute("aria-pressed", String(x === left)));
          state.pick = Number(left.dataset.left);
          return;
        }
        if (right && !right.disabled) {
          if (state.pick === undefined) { setFeedback(null, "First tap a word on the left."); return; }
          const l = box.querySelector(`[data-left="${state.pick}"]`);
          if (Number(right.dataset.right) === state.pick) {
            [l, right].forEach((x) => { x.disabled = true; x.classList.add("matched"); x.setAttribute("aria-pressed", "false"); });
            state.done = (state.done || 0) + 1;
            state.pick = undefined;
            if (state.done === c.pairs.length) answer(!state.misses, state.misses ? "All matched now." : "All matched first time.");
            else setFeedback(null, "");
          } else {
            state.misses = (state.misses || 0) + 1;
            right.classList.add("wrong");
            setTimeout(() => right.classList.remove("wrong"), 600);
            setFeedback(false, `<strong>Not a pair.</strong> Try another meaning for ${mixed(c.pairs[state.pick][0])}.`);
          }
        }
      } else if (c.type === "build") {
        if (answered) return;
        const t = e.target.closest("[data-tile]");
        const placed = e.target.closest("[data-placed]");
        if (t) state.line.push(Number(t.dataset.tile));
        if (placed) state.line = state.line.filter((i) => i !== Number(placed.dataset.placed));
        if (t || placed) {
          box.querySelector(".ls-build").outerHTML = buildHTML(c, state, lang);
          const keep = box.querySelector(t ? ".ls-bank .ls-tile, [data-check]" : ".ls-line .ls-tile, .ls-bank .ls-tile");
          if (keep) keep.focus();
          return;
        }
        if (e.target.closest("[data-check]")) {
          const ok = state.line.every((i, n) => c.tiles[i] === c.tiles[n]);
          box.querySelectorAll(".ls-build .ls-tile").forEach((x) => { x.disabled = true; });
          box.querySelector(".ls-line").classList.add(ok ? "right" : "wrong");
          e.target.closest("[data-check]").disabled = true;
          answer(ok, ok ? c.explain : `The order is: ${c.tiles.join(" ")}. ${c.explain || ""}`);
        }
      } else if (c.type === "parse") {
        if (answered) return;
        const chip = e.target.closest("[data-pick]");
        if (chip) {
          state.picks[chip.dataset.pick] = chip.dataset.value;
          chip.parentElement.querySelectorAll(".ls-chip").forEach((x) => x.setAttribute("aria-pressed", String(x === chip)));
          box.querySelector("[data-check]").disabled = Object.keys(state.picks).length !== c.fields.length;
          return;
        }
        if (e.target.closest("[data-check]")) {
          let ok = true;
          c.fields.forEach((f, fi) => {
            const right = state.picks[fi] === f.answer;
            if (!right) ok = false;
            box.querySelectorAll(`[data-pick="${fi}"]`).forEach((x) => {
              x.disabled = true;
              if (x.dataset.value === f.answer) x.classList.add("right");
              else if (x.getAttribute("aria-pressed") === "true") x.classList.add("wrong");
            });
          });
          e.target.closest("[data-check]").disabled = true;
          answer(ok, c.explain);
        }
      }
    });

    // ---- moving through the lesson
    nextBtn.addEventListener("click", () => {
      if (!answered) return;
      if (p.pos < seq.length - 1) {
        p.pos += 1;
        saveProgress(id, p);
        draw().then(() => { const t = box.querySelector(".ls-title, .ls-big"); if (t) { t.setAttribute("tabindex", "-1"); t.focus({ preventScroll: true }); } });
        window.scrollTo(0, 0);
        return;
      }
      finish();
    });
    backBtn.addEventListener("click", () => {
      if (p.pos === 0) return;
      p.pos -= 1;
      saveProgress(id, p);
      draw();
      window.scrollTo(0, 0);
    });

    const finish = () => {
      const drills = Object.keys(p.first);
      const right = drills.filter((k) => p.first[k]).length;
      // words go to the review list (once each)
      const queue = reviewWords().slice();
      const have = new Set(queue.map((w) => w.k));
      let added = 0;
      L.steps.filter((s) => s.step === "review").forEach((s) => s.cards.forEach((c) => (c.items || []).forEach((w) => {
        if (have.has(w.k)) return;
        have.add(w.k);
        queue.push({ k: w.k, lang, t: w.t, say: w.say, en: w.en, lesson: id, added: new Date().toISOString().slice(0, 10) });
        added++;
      })));
      store.set("reviewQueue", queue);
      const best = Math.max(p.best || 0, drills.length ? Math.round((right / drills.length) * 100) : 100);
      saveProgress(id, { v: 1, sig, done: true, best, completed: new Date().toISOString().slice(0, 10), pos: 0, retries: [], first: {} });
      const next = (index[lang] || []).slice(entries.indexOf(entry) + 1).find((e) => e.file);
      main.querySelector(".ls-stepbar").innerHTML = "";
      main.querySelector(".ls-progress span").style.width = "100%";
      main.querySelector(".ls-nav").hidden = true;
      setFeedback(null, "");
      box.innerHTML = `<div class="ls-done">
        <div class="ls-picture" aria-hidden="true">✓</div>
        <h2 class="ls-title" tabindex="-1">Lesson complete</h2>
        <p>You got <strong>${right} of ${drills.length}</strong> practice questions right first time.</p>
        <p>${added ? `${added} new ${added === 1 ? "word is" : "words are"} in your review list.` : "These words were already in your review list."}</p>
        <div class="ls-done-actions">
          ${next ? `<a class="btn" href="#/lesson/${lang}/${next.id}">Next lesson: ${esc(next.title)}</a>` : ""}
          <a class="btn${next ? " secondary" : ""}" href="#/learn">Back to Learn</a>
          <a class="btn secondary" href="#/review">See your review list</a>
        </div>
      </div>`;
      box.querySelector(".ls-title").focus({ preventScroll: true });
      window.scrollTo(0, 0);
    };

    saveProgress(id, p);
    draw();
  },
};
