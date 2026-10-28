// Videos (Session 11, route #/media): videos for each app lesson, then courses to learn by listening, readings of the
// Bible text, songs and grammar lectures. Content: lessons/media.json (links checked on the date it gives).
import * as store from "./store.js";
import * as data from "./data.js";
import { head } from "./screens.js";
import { lessonIndex, progressOf, nextLesson, mixed } from "./lessons.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const LANG = { grc: "Greek", he: "Hebrew" };
const GLYPH = { grc: "α", he: "א" };

let file = null;
export const mediaList = () => {
  if (!file) file = data.getJSON("lessons/media.json").catch((e) => { file = null; throw e; });
  return file;
};

const linkRow = (v, glyph, lang) => `<li><a class="row" href="${esc(v.href)}" target="_blank" rel="noopener">
    <span class="row-glyph"${glyph === "▶" ? "" : ` lang="${lang}"`} aria-hidden="true">${glyph}</span>
    <span class="row-main"><span class="row-title">${mixed(v.title)}</span>${v.sub ? `<span class="row-sub">${mixed(v.sub)}</span>` : ""}</span>
    <span class="row-end" aria-hidden="true">↗</span>
  </a></li>`;

function lessonsHTML(M, index, lang) {
  const entries = (index[lang] || []).filter((e) => e.file && (M.lessons[e.id] || []).length);
  if (!entries.length) return "";
  const next = nextLesson(index, lang);
  return `<section class="md-lessons">
      <h2>With your lessons</h2>
      <p class="muted">Videos that go with each lesson in this app. The one for your next lesson is open.</p>
      ${entries.map((e) => {
        const p = progressOf(e.id) || {};
        const status = p.done ? "Done" : next && next.id === e.id ? (p.pos ? "Carry on" : "Next") : "";
        return `<details class="md-lesson"${next && next.id === e.id ? " open" : ""}>
          <summary><span class="md-lesson-t">${esc(e.title)}</span>${status ? `<span class="md-status${p.done ? " done" : ""}">${status}</span>` : ""}</summary>
          <ul class="rows">${M.lessons[e.id].map((v) => linkRow(v, "▶", lang)).join("")}</ul>
        </details>`;
      }).join("")}
    </section>`;
}

export const media = {
  title: "Videos",
  async render(main) {
    let lang = store.get("learnLang") === "he" ? "he" : "grc";
    main.innerHTML = `<div class="screen md">
      ${head("Videos", "Hear the languages, and see the grammar explained another way")}
      <div class="switch" role="group" aria-label="Language">
        <button type="button" data-lang="grc" aria-pressed="${lang === "grc"}">Greek</button>
        <button type="button" data-lang="he" aria-pressed="${lang === "he"}">Hebrew</button>
      </div>
      <div class="md-body"><p class="muted">Loading…</p></div>
    </div>`;
    const body = main.querySelector(".md-body");
    let M, index;
    try {
      [M, index] = await Promise.all([mediaList(), lessonIndex().catch(() => ({}))]);
    } catch (e) {
      body.innerHTML = `<div class="note"><p>The list of videos couldn't load. Check your connection and try again.</p>
        <p><button type="button" class="btn secondary" data-retry>Try again</button></p></div>`;
      body.querySelector("[data-retry]").addEventListener("click", () => media.render(main));
      return;
    }
    const draw = () => {
      const m = M[lang];
      body.innerHTML = `${lessonsHTML(m, index, lang)}
        ${m.sections.map((s) => `<section class="md-section">
          <h2>${mixed(s.title)}</h2>
          ${s.sub ? `<p class="muted">${mixed(s.sub)}</p>` : ""}
          <ul class="rows">${s.items.map((v) => linkRow(v, GLYPH[lang], lang)).join("")}</ul>
        </section>`).join("")}
        <p class="muted md-foot">Links open YouTube or the website in a new page; this app stays where you left it. Links checked ${new Date(M.checked + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}.</p>`;
    };
    draw();
    main.querySelectorAll("[data-lang]").forEach((b) => b.addEventListener("click", () => {
      lang = b.dataset.lang;
      main.querySelectorAll("[data-lang]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      draw();
    }));
  },
};

/** The first video for a lesson, for Today's plan (or null). */
export async function firstVideoFor(id) {
  const M = await mediaList();
  const lang = id.indexOf("he-") === 0 ? "he" : "grc";
  return ((M[lang] && M[lang].lessons[id]) || [])[0] || null;
}

