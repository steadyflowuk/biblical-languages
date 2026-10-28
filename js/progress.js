// Progress (Session 11, route #/progress): streak, a calendar of study days, lessons finished, words by how well
// they're known, how much of the Bible text those words make up, letters, the week ahead in Review, and backup.
import * as store from "./store.js";
import * as data from "./data.js";
import { head } from "./screens.js";
import { lessonIndex, progressOf } from "./lessons.js";
import { activity, streak, dayKey, shiftDay, amount } from "./activity.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const LANG = { grc: "Greek", he: "Hebrew" };
const TEXT = { grc: "Greek New Testament", he: "Hebrew Old Testament" };
const LETTERS = { grc: 24, he: 22 };
const DECK = { grc: "data/decks/greek.json", he: "data/decks/hebrew.json" };
const STRONG = 21; // days of stability: "know well" (FSRS expects it remembered three weeks on)
const WEEKS = 12;

const plural = (n, one, many) => `${n.toLocaleString("en-GB")} ${n === 1 ? one : many || one + "s"}`;

// ---------------------------------------------------------------- backup (also used by Settings and Today)

/** Save a backup file: the share sheet in an iPhone/iPad home-screen app, a download elsewhere. Returns a message. */
export async function saveBackup() {
  const name = `aleph-to-omega-backup-${new Date().toISOString().slice(0, 10)}.json`;
  const json = JSON.stringify(store.exportBackup(), null, 2);
  const done = () => { store.set("lastBackup", new Date().toISOString()); return "Backup saved"; };
  // iPhone/iPad home-screen apps can't download files, so use the share sheet ("Save to Files") there.
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const file = typeof File === "function" ? new File([json], name, { type: "application/json" }) : null;
  if (standalone && file && navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: "Aleph to Omega backup" });
      return done();
    } catch (err) {
      return err.name === "AbortError" ? "" : "The backup couldn't be shared. Try again from Safari.";
    }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([json], { type: "application/json" }));
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  return done();
}

/** "today", "yesterday", "3 days ago", "on 12 October" — or "" if never. */
export function whenText(iso, now) {
  if (!iso) return "";
  const at = now || new Date();
  const days = Math.round((new Date(dayKey(at)) - new Date(dayKey(new Date(iso)))) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  return `on ${new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long" })}`;
}

/** Is there enough progress here that losing the phone would hurt, and no backup for a month? */
export function backupDue(now) {
  const cards = Object.keys(store.get("cards") || {}).length;
  const lessonsDone = Object.values(store.get("lessons") || {}).filter((p) => p && p.done).length;
  if (cards < 20 && lessonsDone < 2) return false;
  const last = store.get("lastBackup");
  return !last || (now || new Date()) - new Date(last) > 30 * 86400000;
}

// ---------------------------------------------------------------- the numbers

const deckCache = {};
const deck = (l) => {
  if (!deckCache[l]) deckCache[l] = data.getJSON(DECK[l]).catch(() => { delete deckCache[l]; return null; });
  return deckCache[l];
};

/** Everything the screen shows for one language. */
export async function languageSummary(l, now) {
  const at = now || new Date();
  const [index, d] = await Promise.all([lessonIndex().catch(() => null), deck(l)]);
  const written = index ? (index[l] || []).filter((e) => e.file) : [];
  const done = written.filter((e) => (progressOf(e.id) || {}).done);
  const started = written.filter((e) => { const p = progressOf(e.id) || {}; return !p.done && p.pos; });
  const all = Object.values(store.get("cards") || {}).filter((c) => c.lang === l);
  const words = all.filter((c) => c.src !== "abc");
  const letters = all.filter((c) => c.src === "abc");
  const known = (c) => c.f && c.f.state === 2;
  const strong = words.filter((c) => known(c) && c.f.stability >= STRONG);
  const growing = words.filter((c) => known(c) && c.f.stability < STRONG);
  const learning = words.filter((c) => !known(c));
  // the share of the text: every time a known word appears counts
  let covered = 0;
  let total = 0;
  if (d) {
    total = d.total || 0;
    const counts = d.byKey || (d.byKey = new Map(d.words.map((w) => [w[0], w[3]])));
    words.filter(known).forEach((c) => {
      const k = (d.alias && d.alias[c.k]) || c.k;
      covered += c.n || counts.get(k) || 0;
    });
  }
  return {
    lang: l,
    lessons: { done: done.length, written: written.length, started: started.length, planned: index ? (index[l] || []).length : 0 },
    words: { strong: strong.length, growing: growing.length, learning: learning.length, total: words.length },
    share: total ? Math.min(100, (covered / total) * 100) : null,
    letters: { known: letters.filter(known).length, met: letters.length, total: LETTERS[l] },
    any: done.length + started.length + all.length > 0,
    at,
  };
}

/** Cards due on each of the next 7 days (day 0 = today, including anything overdue). */
export function forecast(now) {
  const at = now || new Date();
  const today = dayKey(at);
  const days = Array.from({ length: 7 }, (_, i) => ({ key: shiftDay(today, -i), n: 0 }));
  Object.values(store.get("cards") || {}).forEach((c) => {
    if (!c.f) return;
    const k = dayKey(new Date(c.f.due));
    const i = k <= today ? 0 : days.findIndex((x) => x.key === k);
    if (i >= 0) days[i].n++;
  });
  return days;
}

// ---------------------------------------------------------------- drawing

function streakHTML(s) {
  const sub = s.current
    ? (s.today ? "You've studied today. Well done." : "Study today to keep it going.")
    : "Do a lesson or a few review cards to start a run of days.";
  return `<section class="pg-streak" aria-label="Days in a row">
      <p class="pg-big"><span class="pg-num">${s.current}</span> ${s.current === 1 ? "day" : "days"} in a row</p>
      <p class="pg-sub">${sub}${s.best > s.current ? ` Your best is ${plural(s.best, "day")}.` : ""}</p>
    </section>`;
}

const LEVELS = [0, 1, 10, 25, 50]; // cards + lesson steps in a day: none, a little … a lot
const level = (n) => LEVELS.reduce((lv, min, i) => (n >= min ? i : lv), 0);

function calendarHTML(now) {
  const a = activity();
  const today = dayKey(now);
  const [y, m, d] = today.split("-").map(Number);
  const weekday = (new Date(y, m - 1, d, 12).getDay() + 6) % 7; // Monday = 0
  const first = shiftDay(today, weekday + (WEEKS - 1) * 7); // the Monday WEEKS-1 weeks back
  let studied = 0;
  let cells = "";
  for (let i = 0; i < WEEKS * 7; i++) {
    const k = shiftDay(first, -i);
    const future = k > today;
    const n = future ? 0 : amount(a, k);
    if (n) studied++;
    const date = new Date(k + "T12:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
    const label = future ? "" : `${date}: ${n ? `${plural(n, "thing")} done` : "no study"}`;
    cells += `<span class="pg-day l${level(n)}${k === today ? " today" : ""}${future ? " future" : ""}"${label ? ` title="${esc(label)}"` : ""}></span>`;
  }
  const days = Math.min(WEEKS * 7, weekday + 1 + (WEEKS - 1) * 7);
  return `<section class="pg-cal-wrap">
      <h2>The last ${WEEKS} weeks</h2>
      <div class="pg-cal" role="img" aria-label="Studied on ${studied} of the last ${days} days">
        <div class="pg-cal-days" aria-hidden="true"><span>Mon</span><span></span><span>Wed</span><span></span><span>Fri</span><span></span><span>Sun</span></div>
        <div class="pg-cal-grid" aria-hidden="true">${cells}</div>
      </div>
      <p class="pg-cal-foot"><span>Studied on <strong>${studied}</strong> of the last ${days} days</span>
        <span class="pg-key" aria-hidden="true">Less <span class="pg-day l0"></span><span class="pg-day l1"></span><span class="pg-day l2"></span><span class="pg-day l3"></span><span class="pg-day l4"></span> More</span></p>
    </section>`;
}

function barHTML(parts, label) {
  const sum = parts.reduce((s, p) => s + p.n, 0);
  return `<div class="pg-bar" role="img" aria-label="${esc(label)}">${sum ? parts.filter((p) => p.n).map((p) => `<span class="${p.cls}" style="flex-grow:${p.n}"></span>`).join("") : ""}</div>`;
}

function languageHTML(s) {
  const l = s.lang;
  if (!s.any) {
    return `<section class="pg-lang">
        <h2>${LANG[l]}</h2>
        <p class="muted">Not started yet.</p>
        <p><a class="btn secondary" href="#/learn" data-learn="${l}">Start the ${LANG[l]} lessons</a></p>
      </section>`;
  }
  const w = s.words;
  const lessonsLine = s.lessons.written
    ? `<p class="pg-line"><strong>${s.lessons.done} of ${s.lessons.written}</strong> lessons finished${s.lessons.started ? ` · ${s.lessons.started} under way` : ""}${s.lessons.planned > s.lessons.written ? ` <span class="muted">(more are being written)</span>` : ""}</p>
      ${barHTML([{ n: s.lessons.done, cls: "s3" }, { n: s.lessons.started, cls: "s1" }, { n: s.lessons.written - s.lessons.done - s.lessons.started, cls: "s0" }], `${s.lessons.done} of ${s.lessons.written} lessons finished`)}`
    : "";
  const share = s.share === null ? "" : `
      <div class="pg-share">
        <p class="pg-line">The words you know make up <strong>${s.share < 10 ? s.share.toFixed(1) : Math.round(s.share)}%</strong> of the ${TEXT[l]}.</p>
        ${barHTML([{ n: s.share, cls: "s3" }, { n: 100 - s.share, cls: "s0" }], `${Math.round(s.share)}% of the ${TEXT[l]}`)}
        <p class="muted pg-note">Every time a word you know appears counts, so common words like ${l === "he" ? "<span lang=\"he\">וְ</span> and <span lang=\"he\">אֱלֹהִים</span>" : "<span lang=\"grc\">ὁ</span> and <span lang=\"grc\">καί</span>"} soon add up. A word counts as known once you've remembered it in Review.</p>
      </div>`;
  const letters = s.letters.met
    ? `<p class="pg-line"><strong>${s.letters.known} of ${s.letters.total}</strong> letters known <a class="pg-link" href="#/alphabet/${l}">Alphabet guide</a></p>`
    : "";
  return `<section class="pg-lang">
      <h2>${LANG[l]}</h2>
      ${lessonsLine}
      <p class="pg-line"><strong>${plural(w.total, "word")}</strong> in Review</p>
      ${w.total ? `${barHTML([{ n: w.strong, cls: "s3" }, { n: w.growing, cls: "s2" }, { n: w.learning, cls: "s1" }], `${w.strong} known well, ${w.growing} getting there, ${w.learning} still new`)}
      <ul class="pg-legend">
        <li><span class="pg-swatch s3" aria-hidden="true"></span>Known well <strong>${w.strong}</strong></li>
        <li><span class="pg-swatch s2" aria-hidden="true"></span>Getting there <strong>${w.growing}</strong></li>
        <li><span class="pg-swatch s1" aria-hidden="true"></span>Still new <strong>${w.learning}</strong></li>
      </ul>` : `<p class="muted">Words from your lessons appear here once you've reviewed them.</p>`}
      ${share}
      ${letters}
    </section>`;
}

function forecastHTML(days) {
  const max = Math.max(1, ...days.map((d) => d.n));
  const name = (d, i) => (i === 0 ? "Today" : new Date(d.key + "T12:00:00").toLocaleDateString("en-GB", { weekday: "short" }));
  const total = days.reduce((s, d) => s + d.n, 0);
  return `<section class="pg-week">
      <h2>The week ahead in Review</h2>
      ${total ? `<ol class="pg-fc">${days.map((d, i) => `<li>
          <span class="pg-fc-n">${d.n}</span>
          <span class="pg-fc-bar"><span style="height:${d.n ? Math.max(6, Math.round((d.n / max) * 100)) : 0}%"></span></span>
          <span class="pg-fc-day">${name(d, i)}</span>
          <span class="visually-hidden">: ${plural(d.n, "word")} due</span></li>`).join("")}</ol>
        <p class="muted">Words come back just before you'd forget them, so the numbers change as you answer. New words aren't counted here.</p>`
        : `<p class="muted">Nothing is due this week yet.</p>`}
    </section>`;
}

const lastBackupText = (now) => {
  const last = store.get("lastBackup");
  return `Your progress is kept on this device only. ${last ? `Last backup saved ${whenText(last, now)}.` : "You haven't saved a backup yet."}`;
};

function backupHTML(now) {
  return `<section class="pg-backup" id="backup">
      <h2>Backup</h2>
      <p class="pg-backup-last">${lastBackupText(now)}</p>
      <p class="btn-row"><button type="button" class="btn${backupDue(now) ? "" : " secondary"}" data-backup>Save a backup</button>
        <a class="btn secondary" href="#/settings">Restore one in Settings</a></p>
    </section>`;
}

export const progress = {
  title: "Progress",
  async render(main) {
    const now = new Date();
    const first = store.get("learnLang") === "he" ? "he" : "grc";
    const langs = [first, first === "he" ? "grc" : "he"];
    main.innerHTML = `<div class="screen pg">
      ${head("Progress", "How your Greek and Hebrew are coming along")}
      ${streakHTML(streak(now))}
      ${calendarHTML(now)}
      <div class="pg-langs"><p class="muted">Adding up…</p></div>
      ${forecastHTML(forecast(now))}
      ${backupHTML(now)}
    </div>`;
    main.querySelector("[data-backup]").addEventListener("click", async () => {
      const msg = await saveBackup();
      if (msg) toast(msg);
      const p = main.querySelector(".pg-backup-last");
      if (p) p.textContent = lastBackupText(new Date());
    });
    const sums = await Promise.all(langs.map((l) => languageSummary(l, now)));
    const slot = main.querySelector(".pg-langs");
    if (!slot) return; // moved on
    slot.innerHTML = sums.map(languageHTML).join("");
    slot.querySelectorAll("[data-learn]").forEach((a) => a.addEventListener("click", () => store.set("learnLang", a.dataset.learn)));
  },
};

function toast(message) {
  document.querySelector(".toast")?.remove();
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  el.textContent = message;
  document.body.append(el);
  setTimeout(() => el.remove(), 3200);
}
