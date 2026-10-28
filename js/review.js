// Review trainer (Session 9): flashcards scheduled by FSRS (ts-fsrs, vendored in js/vendor).
// Words come from finished lessons (ao:reviewQueue) and, if switched on, the frequency decks (data/decks/*.json).
// A word becomes a card the first time it's shown; until then it costs nothing in storage.
//
// Store:
//   cards        { "grc:G3056": { id, lang, k, t, say, en, src: "lesson"|"deck", lesson, n, added, f: fsrs card } }
//   reviewLog    { "2026-10-28": { r: reviews, n: new words } }  (the day starts at 4am, like most flashcard apps)
//   reviewDecks  { grc: false, he: false }   newPerDay 10   reviewLang "all"|"grc"|"he"   reviewAutoPlay false
import * as store from "./store.js";
import * as data from "./data.js";
import { fsrs, generatorParameters, createEmptyCard, Rating, State } from "./vendor/ts-fsrs.js";
import { greekSay } from "./sound.js";
import { sayButton, play } from "./audio.js";
import { head } from "./screens.js";
import { mixed } from "./lessons.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const scheduler = fsrs(generatorParameters({ enable_fuzz: true, maximum_interval: 3650 }));
const LANG_NAME = { grc: "Greek", he: "Hebrew" };
const DECK_FILE = { grc: "data/decks/greek.json", he: "data/decks/hebrew.json" };
const DAY_START = 4; // hours after midnight
const LEARN_AHEAD = 20 * 60 * 1000; // a word due again within 20 minutes comes back in this session

// ---------------------------------------------------------------- days and storage

/** The review day a moment belongs to ("2026-10-28"); it starts at 4am. */
export function dayKey(d) {
  const x = new Date((d || new Date()).getTime() - DAY_START * 3600 * 1000);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
}

/** When the current review day ends (the next 4am). */
export function dayEnd(now) {
  const n = now || new Date();
  const end = new Date(n);
  end.setHours(DAY_START, 0, 0, 0);
  if (end <= n) end.setDate(end.getDate() + 1);
  return end;
}

export const cards = () => store.get("cards") || {};
const saveCards = (c) => store.set("cards", c);
const log = () => store.get("reviewLog") || {};

function bump(field, now) {
  const L = log();
  const d = dayKey(now);
  L[d] = L[d] || { r: 0, n: 0 };
  L[d][field] += 1;
  // keep about three months
  Object.keys(L).sort().slice(0, -100).forEach((k) => { delete L[k]; });
  store.set("reviewLog", L);
}

export const newToday = (now) => (log()[dayKey(now)] || {}).n || 0;
export const reviewedToday = (now) => (log()[dayKey(now)] || {}).r || 0;

// FSRS card <-> what we store (dates as text)
function toFsrs(f) {
  return Object.assign({}, f, { due: new Date(f.due), last_review: f.last_review ? new Date(f.last_review) : undefined });
}
function fromFsrs(c) {
  const out = {};
  ["stability", "difficulty", "elapsed_days", "scheduled_days", "reps", "lapses", "learning_steps", "state"].forEach((k) => { out[k] = c[k]; });
  out.due = new Date(c.due).toISOString();
  if (c.last_review) out.last_review = new Date(c.last_review).toISOString();
  return out;
}

// ---------------------------------------------------------------- decks

const deckCache = {};
/** A frequency deck: { lang, min, words: [[key, lemma, gloss, count, say]], alias } — or null offline. */
export function deck(lang) {
  if (!deckCache[lang]) {
    deckCache[lang] = data.getJSON(DECK_FILE[lang]).catch(() => { delete deckCache[lang]; return null; });
  }
  return deckCache[lang];
}

const deckSettings = () => Object.assign({ grc: false, he: false }, store.get("reviewDecks") || {});

/** The id a word's card goes by: the deck's main sense when the lexicon splits senses (κύριος, בֵּן). */
const cardId = (lang, key, decks) => `${lang}:${(decks[lang] && decks[lang].alias[key]) || key}`;

// ---------------------------------------------------------------- today's plan

/**
 * What's waiting: { due: [card], fresh: [card to introduce], newLeft, langs: {grc, he}, decks }
 * lang: "all" | "grc" | "he". Due = every card due before the review day ends; fresh = new words up to today's limit:
 * lesson words first (in the order they were learnt), then the switched-on decks, most common first.
 */
export async function plan(lang, now) {
  const at = now || new Date();
  const want = (l) => !lang || lang === "all" || lang === l;
  const settings = deckSettings();
  const decks = {};
  await Promise.all(["grc", "he"].map(async (l) => { decks[l] = await deck(l); }));
  const all = cards();
  const end = dayEnd(at).getTime();
  const due = Object.values(all).filter((c) => c.f && want(c.lang) && new Date(c.f.due).getTime() <= end)
    .sort((a, b) => new Date(a.f.due) - new Date(b.f.due));
  const newLeft = Math.max(0, (Number(store.get("newPerDay")) || 10) - newToday(at));
  const fresh = [];
  const seen = new Set(Object.keys(all));
  const offer = (c) => { if (!seen.has(c.id)) { seen.add(c.id); fresh.push(c); } };
  let upgraded = false;
  (store.get("reviewQueue") || []).forEach((w) => {
    const l = w.lang === "he" ? "he" : "grc";
    const id = cardId(l, w.k, decks);
    const c = all[id];
    if (c && c.src === "deck") { // met in a list first, then in a lesson: the lesson's wording is better
      Object.assign(c, { t: w.t, say: w.say, en: w.en, src: "lesson", lesson: w.lesson });
      upgraded = true;
    }
    if (want(l)) offer({ id, lang: l, k: w.k, t: w.t, say: w.say, en: w.en, src: "lesson", lesson: w.lesson });
  });
  // list cards follow corrections to the lists (wording, pronunciation, counts)
  Object.values(all).forEach((c) => {
    if (c.src !== "deck" || !decks[c.lang]) return;
    const w = (decks[c.lang].byKey || (decks[c.lang].byKey = new Map(decks[c.lang].words.map((x) => [x[0], x])))).get(c.k);
    if (w && (c.en !== w[2] || (c.say || "") !== (w[4] || "") || c.n !== w[3])) {
      Object.assign(c, { t: w[1], en: w[2], say: w[4] || "", n: w[3] });
      upgraded = true;
    }
  });
  if (upgraded) saveCards(all);
  ["grc", "he"].forEach((l) => {
    if (!want(l) || !settings[l] || !decks[l]) return;
    decks[l].words.forEach(([k, t, en, n, say]) => offer({ id: `${l}:${k}`, lang: l, k, t, say: say || "", en, n, src: "deck" }));
  });
  const langs = { grc: false, he: false };
  Object.values(all).forEach((c) => { langs[c.lang] = true; });
  (store.get("reviewQueue") || []).forEach((w) => { langs[w.lang === "he" ? "he" : "grc"] = true; });
  ["grc", "he"].forEach((l) => { if (settings[l]) langs[l] = true; });
  return { due, fresh: fresh.slice(0, newLeft), freshTotal: fresh.length, newLeft, langs, decks };
}

/** How many words are waiting today (for Today's row). */
export async function waitingCount(now) {
  const p = await plan("all", now);
  return { due: p.due.length, fresh: p.fresh.length, total: p.due.length + p.fresh.length };
}

// ---------------------------------------------------------------- rating

/** The four choices for a card now: [{ rating, label, when, card }] — card is the FSRS result, not yet saved. */
export function choices(card, now) {
  const at = now || new Date();
  const f = card.f ? toFsrs(card.f) : createEmptyCard(at);
  const out = scheduler.repeat(f, at);
  return [Rating.Again, Rating.Hard, Rating.Good, Rating.Easy].map((r) => ({
    rating: r,
    label: { [Rating.Again]: "Again", [Rating.Hard]: "Hard", [Rating.Good]: "Good", [Rating.Easy]: "Easy" }[r],
    when: interval(out[r].card.due - at),
    card: out[r].card,
  }));
}

/** "1 min", "10 min", "3 hours", "2 days", "4 months", "1.5 years" */
export function interval(ms) {
  const min = Math.max(1, Math.round(ms / 60000));
  if (min < 60) return `${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} ${h === 1 ? "hour" : "hours"}`;
  const d = Math.round(min / 1440);
  if (d < 31) return `${d} ${d === 1 ? "day" : "days"}`;
  const mo = Math.round(d / 30.4);
  if (mo < 12) return `${mo} ${mo === 1 ? "month" : "months"}`;
  const y = Math.round((d / 365) * 10) / 10;
  return `${y} ${y === 1 ? "year" : "years"}`;
}

/** Save a rating; returns the updated card. A new word becomes a card here. */
export function rate(card, rating, now) {
  const at = now || new Date();
  const pick = choices(card, at).find((c) => c.rating === rating);
  const all = cards();
  const isNew = !card.f;
  const saved = Object.assign({}, all[card.id] || card, { f: fromFsrs(pick.card) });
  if (isNew) saved.added = dayKey(at);
  all[card.id] = saved;
  saveCards(all);
  bump("r", at);
  if (isNew) bump("n", at);
  return saved;
}

// ---------------------------------------------------------------- screen

const sayOf = (c) => (c.lang === "grc" ? greekSay(c.t) : c.say || "");

function relativeDue(f, now) {
  const at = now || new Date();
  const due = new Date(f.due);
  if (due <= dayEnd(at)) return "today";
  const days = Math.round((due - dayEnd(at)) / 86400000) + 1;
  return days === 1 ? "tomorrow" : `in ${interval(due - at)}`;
}

function summaryHTML(p, lang) {
  const total = p.due.length + p.fresh.length;
  const parts = [];
  if (p.due.length) parts.push(`${p.due.length} to review`);
  if (p.fresh.length) parts.push(`${p.fresh.length} new`);
  const mins = Math.max(1, Math.round((p.due.length * 8 + p.fresh.length * 15) / 60));
  if (total) {
    return `<section class="rv-summary">
      <p class="rv-big">${total} ${total === 1 ? "word" : "words"}</p>
      <p class="rv-sub">${parts.join(" · ")} · about ${mins} ${mins === 1 ? "minute" : "minutes"}</p>
      <p><button type="button" class="btn rv-start" data-start>Start</button></p>
    </section>`;
  }
  const all = Object.values(cards()).filter((c) => c.f && (lang === "all" || c.lang === lang));
  const next = all.map((c) => new Date(c.f.due)).sort((a, b) => a - b)[0];
  const nothingYet = !all.length;
  return `<section class="rv-summary done">
    <p class="rv-big">${nothingYet ? "Nothing to review yet" : "All done for today"}</p>
    <p class="rv-sub">${nothingYet ? "Finish a lesson, or switch on a list of common words below." : next ? `Your next words come back ${relativeDue({ due: next.toISOString() })}.` : ""}${!nothingYet && p.freshTotal && !p.newLeft ? " You've met today's new words; more tomorrow." : ""}</p>
    ${nothingYet ? `<p><a class="btn" href="#/learn">Start a lesson</a></p>` : ""}
  </section>`;
}

function listsHTML(p) {
  const s = deckSettings();
  const lessonWords = (store.get("reviewQueue") || []).length;
  const per = Number(store.get("newPerDay")) || 10;
  const deckRow = (l) => `<label class="toggle"><input type="checkbox" data-deck="${l}"${s[l] ? " checked" : ""}>
      <span>The ${p.decks[l] ? p.decks[l].words.length : ""} most common ${LANG_NAME[l]} words
      <span class="muted">${l === "grc" ? "Each used 50 times or more: together about 80% of the words in the New Testament." : "Each used 50 times or more in the Old Testament."} Most common first.</span></span></label>`;
  return `<h2>What you review</h2>
    <div class="rv-lists">
      <p class="rv-line"><strong>Words from your lessons</strong> <span class="muted">${lessonWords} so far, always included</span></p>
      ${deckRow("grc")}
      ${deckRow("he")}
      <label class="rv-select">New words a day
        <select data-per-day>${[5, 10, 15, 20, 30].map((n) => `<option value="${n}"${n === per ? " selected" : ""}>${n}</option>`).join("")}</select>
      </label>
      <label class="toggle"><input type="checkbox" data-autoplay${store.get("reviewAutoPlay") ? " checked" : ""}>
        <span>Say each word aloud <span class="muted">Plays the word as each card appears.</span></span></label>
    </div>`;
}

function wordListHTML(lang) {
  const all = Object.values(cards()).filter((c) => c.f && (lang === "all" || c.lang === lang));
  if (!all.length) return "";
  const groups = ["grc", "he"].map((l) => [l, all.filter((c) => c.lang === l).sort((a, b) => new Date(a.f.due) - new Date(b.f.due))]).filter(([, cs]) => cs.length);
  return `<h2>Your words</h2>
    ${groups.map(([l, cs]) => `<details class="rv-words">
      <summary>${LANG_NAME[l]} <span class="muted">${cs.length}</span></summary>
      <ul class="rows">${cs.map((c) => `<li><a class="row" href="#/words/${encodeURIComponent(c.k)}">
        <span class="row-main"><span class="row-title review-t" lang="${l === "he" ? "he" : "grc"}"${l === "he" ? ' dir="rtl"' : ""}>${esc(c.t)}</span>
        <span class="row-sub">${esc(sayOf(c))} · ${mixed(c.en)}</span></span>
        <span class="row-end rv-due">${esc(relativeDue(c.f))}</span></a></li>`).join("")}</ul>
    </details>`).join("")}`;
}

function cardHTML(c, shown, pos, count) {
  const he = c.lang === "he";
  const status = !c.f ? "New word" : c.f.state === State.Review ? "Review" : "Learning";
  const opts = shown ? choices(c) : [];
  return `<div class="rv-session">
    <div class="rv-top">
      <button type="button" class="ls-close" data-stop aria-label="Stop reviewing"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
      <p class="rv-count" role="status">${pos} of ${count}</p>
    </div>
    <div class="rv-card${shown ? " shown" : ""}">
      <p class="rv-meta">${LANG_NAME[c.lang]} · ${status}${c.src === "lesson" ? " · from your lessons" : ""}</p>
      <p class="rv-word" lang="${he ? "he" : "grc"}"${he ? ' dir="rtl"' : ""} tabindex="-1">${esc(c.t)}</p>
      <p class="rv-listen">${sayButton(c.t, c.lang, { label: "Listen" })}</p>
      ${shown ? `<div class="rv-answer">
          <p class="rv-say">${esc(sayOf(c))}</p>
          <p class="rv-en">${mixed(c.en)}</p>
          <p class="rv-more"><a href="#/words/${encodeURIComponent(c.k)}">Dictionary entry</a>${c.n ? ` · used ${c.n.toLocaleString("en-GB")} times` : ""}</p>
        </div>
        <p class="rv-ask">How well did you know it?</p>
        <div class="rv-rate" role="group" aria-label="How well did you know it?">
          ${opts.map((o, i) => `<button type="button" class="rv-btn r${o.rating}" data-rate="${o.rating}"><span class="rv-btn-label">${o.label}</span><span class="rv-btn-when">${esc(o.when)}</span><span class="visually-hidden">, comes back in ${esc(o.when)}. Key ${i + 1}</span></button>`).join("")}
        </div>
        <p class="muted rv-keys">Again if you didn't know it; Good if you did; Easy if it came at once.</p>`
      : `<p><button type="button" class="btn rv-show" data-show>Show the answer</button></p>`}
    </div>
  </div>`;
}

let keyHandler = null;

export const reviewScreen = {
  title: "Review",
  async render(main) {
    if (keyHandler) { document.removeEventListener("keydown", keyHandler); keyHandler = null; }
    const lang = store.get("reviewLang") || "all";
    main.innerHTML = `<div class="screen">${head("Review", "A few minutes a day keeps words from fading")}<p class="muted">Loading…</p></div>`;
    let p;
    try {
      p = await plan(lang);
    } catch (e) {
      main.innerHTML = `<div class="screen">${head("Review", "")}<div class="note"><p>Your review couldn't load. Check your connection and try again.</p></div>
        <p><button type="button" class="btn" data-retry>Try again</button></p></div>`;
      main.querySelector("[data-retry]").addEventListener("click", () => this.render(main));
      return;
    }
    if (!location.hash.startsWith("#/review")) return; // left while loading
    const both = p.langs.grc && p.langs.he;
    main.innerHTML = `<div class="screen rv">
      ${head("Review", "A few minutes a day keeps words from fading")}
      ${both ? `<div class="switch" role="group" aria-label="Language">${[["all", "Both"], ["grc", "Greek"], ["he", "Hebrew"]].map(([v, t]) => `<button type="button" data-rv-lang="${v}" aria-pressed="${lang === v}">${t}</button>`).join("")}</div>` : ""}
      ${summaryHTML(p, lang)}
      ${listsHTML(p)}
      ${wordListHTML(lang)}
      ${!p.decks.grc || !p.decks.he ? `<p class="muted">The word lists need a connection the first time they load.</p>` : ""}
    </div>`;
    main.querySelectorAll("[data-rv-lang]").forEach((b) => b.addEventListener("click", () => { store.set("reviewLang", b.dataset.rvLang); this.render(main); }));
    main.querySelectorAll("[data-deck]").forEach((cb) => cb.addEventListener("change", () => {
      const s = deckSettings();
      s[cb.dataset.deck] = cb.checked;
      store.set("reviewDecks", s);
      this.render(main);
    }));
    const per = main.querySelector("[data-per-day]");
    per.addEventListener("change", () => { store.set("newPerDay", Number(per.value)); this.render(main); });
    main.querySelector("[data-autoplay]").addEventListener("change", (e) => store.set("reviewAutoPlay", e.target.checked));
    const start = main.querySelector("[data-start]");
    if (start) start.addEventListener("click", () => this.session(main, p.due.concat(p.fresh)));
  },

  /** A review session over queue (cards and new words). Words due again within 20 minutes come back before the end. */
  session(main, queue) {
    const q = queue.slice();
    let pos = 0;
    const total = () => pos + q.length;
    let reviewed = 0;
    let shown = false;
    const draw = (focus) => {
      if (!q.length) return finish();
      main.innerHTML = cardHTML(q[0], shown, pos + 1, total());
      main.querySelector("[data-stop]").addEventListener("click", () => this.render(main));
      const show = main.querySelector("[data-show]");
      if (show) show.addEventListener("click", () => { shown = true; draw("rate"); });
      main.querySelectorAll("[data-rate]").forEach((b) => b.addEventListener("click", () => answer(Number(b.dataset.rate))));
      if (focus === "rate") main.querySelector(`[data-rate="${Rating.Good}"]`).focus();
      else if (focus !== "none") (show || main.querySelector(".rv-word")).focus();
      if (!shown && store.get("reviewAutoPlay")) {
        const b = main.querySelector(".rv-listen [data-say]");
        if (b) play(b);
      }
    };
    const answer = (rating) => {
      const card = rate(q.shift(), rating);
      reviewed += 1;
      shown = false;
      if (new Date(card.f.due) - new Date() < LEARN_AHEAD) q.splice(Math.min(3, q.length), 0, card); // back in a few cards
      else pos += 1; // done with this word for today
      draw();
    };
    const finish = () => {
      if (keyHandler) { document.removeEventListener("keydown", keyHandler); keyHandler = null; }
      main.innerHTML = `<div class="screen rv">
        <div class="rv-done" tabindex="-1">
          <p class="rv-tick" aria-hidden="true">✓</p>
          <h1>Done for now</h1>
          <p>${reviewed} ${reviewed === 1 ? "answer" : "answers"} saved. Each word will come back just before you'd forget it.</p>
          <div class="btn-row"><a class="btn" href="#/today">Back to Today</a><button type="button" class="btn secondary" data-back>Review page</button></div>
        </div>
      </div>`;
      main.querySelector("[data-back]").addEventListener("click", () => this.render(main));
      main.querySelector(".rv-done").focus();
    };
    keyHandler = (e) => {
      if (!location.hash.startsWith("#/review") || !main.querySelector(".rv-session")) return;
      if (e.target.closest && e.target.closest("input, select, textarea")) return;
      if (!shown && (e.key === " " || e.key === "Enter") && !(e.target.closest && e.target.closest("button, a"))) { e.preventDefault(); shown = true; draw("rate"); }
      else if (shown && /^[1-4]$/.test(e.key)) { e.preventDefault(); answer(Number(e.key)); }
    };
    document.addEventListener("keydown", keyHandler);
    draw();
  },
};
