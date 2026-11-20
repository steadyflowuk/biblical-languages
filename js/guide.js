// The Guide tab (19 Nov 2026): explanations of every word, sign and idea a beginner meets in the app.
// Routes: #/guide (search + sections) · #/guide/s/SECTION · #/guide/ENTRY · #/guide/code/LANG/CODE (what each part of
// a grammar label means). Content: guide/guide.json + guide/examples.json, built from guide/src/*.md by
// tools/build_guide.py (format: guide/README.md). Text rendering, label reading and search: js/guide-text.js.
import * as data from "./data.js";
import * as nav from "./nav.js";
import { head } from "./screens.js";
import { friendlyGrammar, englishHTML } from "./reader.js";
import { heFriendlyGrammar, heEnglish, heTranslit } from "./hebrew.js";
import { buildVerse } from "./votd.js";
import { sayButton } from "./audio.js";
import { greekSay } from "./sound.js";
import { esc, renderText, labelTerms, phraseTable, searchGuide, looksLikeCode, codeLang, explainLink, linkText } from "./guide-text.js";

let loaded = null;
/** The guide and its examples, with lookups ready. */
export function loadGuide() {
  if (!loaded) {
    loaded = Promise.all([data.getJSON("guide/guide.json"), data.getJSON("guide/examples.json")]).then(([g, x]) => {
      const entries = Object.fromEntries(g.entries.map((e) => [e.id, e]));
      const sectionOf = Object.fromEntries(g.sections.map((s) => [s.id, s]));
      return { ...g, byId: entries, sectionOf, examples: x.examples, voices: x.words, table: phraseTable(g) };
    }).catch((e) => { loaded = null; throw e; });
  }
  return loaded;
}

const ctxFor = (g, e) => ({ entries: g.byId, books: g.books, counts: (e && e.counts) || {}, voices: g.voices });
const WHERE = { grc: "New Testament", he: "Old Testament (Hebrew)", arc: "Old Testament (Aramaic)" };
let lastQuery = "";

// ---------------------------------------------------------------- the pieces of a page

function blockHTML(b, ctx) {
  if (b.p) return `<p>${renderText(b.p, ctx)}</p>`;
  if (b.h) return `<h2 class="g-h">${renderText(b.h, ctx)}</h2>`;
  if (b.ul) return `<ul class="g-list">${b.ul.map((x) => `<li>${renderText(x, ctx)}</li>`).join("")}</ul>`;
  if (b.table) {
    const t = b.table;
    return `<div class="g-table-wrap"><table class="g-table">${t.caption ? `<caption>${renderText(t.caption, ctx)}</caption>` : ""}
      <thead><tr>${t.head.map((h) => `<th scope="col">${renderText(h, ctx)}</th>`).join("")}</tr></thead>
      <tbody>${t.rows.map((r) => `<tr>${r.map((c, i) => (i === 0 ? `<th scope="row">${renderText(c, ctx)}</th>` : `<td>${renderText(c, ctx)}</td>`)).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  return "";
}

/** The grammar of a word as the app shows it, from its code (Greek parts joined by +, Hebrew parts by /). */
export function labelOf(code, lang, morph) {
  if (lang === "grc") return String(code).split("+").map((c) => friendlyGrammar((morph[c] || [c])[0])).join(" + ");
  const parts = String(code).replace(/^[HA]/, "").split("/");
  const L = String(code).charAt(0);
  return parts.map((p) => heFriendlyGrammar((morph[L + p] || [L + p])[0])).join(" + ");
}


function exampleHTML(x, g, morph) {
  const lang = x.lang;
  const he = lang === "he";
  const v = buildVerse({ lang, bookId: x.book, ch: x.ch, v: x.v, name: "", words: x.words, lex: x.lex, morph, english: x.english });
  const w = v.words[x.wi];
  const raw = x.words[x.wi];
  const words = v.words.map((it, i) => `${it.pre ? esc(it.pre) : ""}<span class="${i === x.wi ? "g-hit" : ""}">${esc(it.t)}</span>${esc(String(it.p || "").replace(/[¶¬]/g, ""))}`)
    .reduce((out, h, i) => out + (i && !String(v.words[i - 1].p || "").endsWith("־") ? " " : "") + h, "");
  const translit = he ? heTranslit(raw[1]) : raw[1];
  const say = he ? "" : greekSay(w.t);
  const code = raw[4] || "";
  const label = labelOf(code, lang, morph);
  return `<li class="g-ex">
    <p class="g-ex-ref"><a href="#/read/${x.book}/${x.ch}/${x.v}/${x.wi}">${esc(x.ref)}</a></p>
    <p class="g-ex-verse" lang="${lang}" dir="${he ? "rtl" : "ltr"}">${words}</p>
    <p class="g-ex-en">${esc(x.english.replace(/\u0001\d+\u0001/g, ""))}</p>
    <div class="g-ex-word">
      <p class="g-ex-form"><span lang="${lang}"${he ? ' dir="rtl"' : ""}>${esc(w.t)}</span>${sayButton(w.say, lang, { className: "small" })}
        <span class="muted">${esc(translit)}${say ? ` · ${esc(say)}` : ""}</span></p>
      <p class="g-ex-mean">${englishHTML(he ? heEnglish(w.en) : w.en) || esc(w.gloss)}</p>
      <p class="g-ex-gram">${esc(label)} ${explainLink(lang, code)}</p>
      ${x.note ? `<p class="g-ex-note">${renderText(x.note, ctxFor(g))}</p>` : ""}
    </div>
    <p class="g-ex-actions">${sayButton(v.spoken, lang, { label: "Listen to the verse" })}
      <a class="verse-link" href="#/read/${x.book}/${x.ch}/${x.v}/${x.wi}">Open in the Reader</a></p>
  </li>`;
}

const rowHTML = (e, g, extra) => `<li><a class="row" href="#/guide/${esc(e.id)}"><span class="row-main">
  <span class="row-title">${esc(e.title)}</span><span class="row-sub">${extra ? `${esc(extra)} · ` : ""}${renderPlain(e.short, g)}</span></span></a></li>`;
// a row's summary without buttons inside the link
const renderPlain = (s, g) => esc(String(s || "").replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, id, w) => w || (g.byId[id] ? linkText(g.byId[id]) : id))
  .replace(/\[([1-3]?[A-Z]{2,3}) (\d+):(\d+)(?:\|([^\]]+))?\]/g, (m, bk, c, v, w) => w || `${g.books[bk] || bk} ${c}:${v}`).replace(/\*([^*]+)\*/g, "$1"));

// ---------------------------------------------------------------- screens

function homeHTML(g) {
  return `<div class="screen guide">
    ${head("Guide", "What every word, sign and idea in the app means")}
    <form class="dict-search g-search" role="search">
      <label class="sr" for="guide-q">Search the guide</label>
      <input id="guide-q" type="search" placeholder="A word, abbreviation or grammar code" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="search" value="${esc(lastQuery)}">
    </form>
    <p class="field-help">Try “aorist”, “dagesh”, “3ms”, “impf.” or V-2AAI-3S.</p>
    <p class="sr" role="status" aria-live="polite" data-status></p>
    <div class="g-results"></div>
    <div class="g-sections">
      ${g.sections.map((s, i) => `<h2>${esc(s.title)}</h2>
        ${i === 0 ? `<div class="g-intro">${s.intro.map((p) => `<p>${renderText(p, ctxFor(g))}</p>`).join("")}</div>` : ""}
        <ul class="rows">${i === 0 ? s.entries.map((id) => rowHTML(g.byId[id], g)).join("")
          : `<li><a class="row" href="#/guide/s/${esc(s.id)}"><span class="row-main"><span class="row-title">${esc(s.title)}</span>
             <span class="row-sub">${esc(firstSentence(s.intro[0] || ""))}</span></span><span class="row-end">${s.entries.length}</span></a></li>`}</ul>`).join("")}
    </div>
  </div>`;
}

const firstSentence = (s) => String(s).replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2").replace(/\[\[([^\]]+)\]\]/g, "$1").replace(/([.!?])\s.*$/, "$1"); // no look-behind: iOS < 16.4

function sectionHTML(g, s) {
  const i = g.sections.indexOf(s);
  return `<div class="screen guide">
    <p class="g-crumb"><a href="#/guide">Guide</a></p>
    ${head(s.title)}
    <div class="g-intro">${s.intro.map((p) => `<p>${renderText(p, ctxFor(g))}</p>`).join("")}</div>
    <ul class="rows">${s.entries.map((id) => rowHTML(g.byId[id], g)).join("")}</ul>
    <nav class="g-pager" aria-label="Sections">
      ${i > 0 ? `<a class="btn secondary" href="#/guide/s/${g.sections[i - 1].id}">‹ ${esc(g.sections[i - 1].title)}</a>` : "<span></span>"}
      ${i < g.sections.length - 1 ? `<a class="btn secondary" href="#/guide/s/${g.sections[i + 1].id}">${esc(g.sections[i + 1].title)} ›</a>` : ""}
    </nav>
  </div>`;
}

function entryHTML(g, e) {
  const s = g.sectionOf[e.section];
  const ctx = ctxFor(g, e);
  const ids = s.entries;
  const i = ids.indexOf(e.id);
  const prev = g.byId[ids[i - 1]];
  const next = g.byId[ids[i + 1]];
  const counts = (e.count || []).map((c) => `${WHERE[c.lang]}: ${c.n.toLocaleString("en-GB")} ${c.n === 1 ? "word" : "words"}`);
  return `<div class="screen guide g-entry">
    <p class="g-crumb"><a href="#/guide">Guide</a> › <a href="#/guide/s/${esc(s.id)}">${esc(s.title)}</a></p>
    <h1 class="g-title">${renderText(e.title, ctx)}</h1>
    ${e.aka && e.aka.length ? `<p class="g-aka">Also called or written: ${e.aka.map((a) => renderText(a, ctx)).join(", ")}</p>` : ""}
    <p class="g-short">${renderText(e.short, ctx)}</p>
    <div class="g-body">${(e.body || []).map((b) => blockHTML(b, ctx)).join("")}</div>
    ${counts.length ? `<p class="g-count">How often: ${counts.map(esc).join(" · ")}.</p>` : ""}
    ${(g.examples[e.id] || []).length ? `<h2 class="g-h">In the Bible</h2><ul class="g-examples" data-examples="${esc(e.id)}"><li class="muted">Loading the examples…</li></ul>` : ""}
    ${e.see && e.see.length ? `<h2 class="g-h">See also</h2><ul class="g-see">${e.see.filter((id) => g.byId[id]).map((id) => `<li><a href="#/guide/${esc(id)}">${esc(g.byId[id].title)}</a></li>`).join("")}</ul>` : ""}
    ${e.lessons && e.lessons.length ? `<p class="g-lessons">Taught in: ${e.lessons.map((l) => `<a href="#/lesson/${l.split("-")[0]}/${esc(l)}">lesson ${esc(l.split("-")[1])} (${l.startsWith("he") ? "Hebrew" : "Greek"})</a>`).join(", ")}</p>` : ""}
    <nav class="g-pager" aria-label="Entries in this section">
      ${prev ? `<a class="btn secondary" href="#/guide/${esc(prev.id)}">‹ ${esc(prev.title)}</a>` : "<span></span>"}
      ${next ? `<a class="btn secondary" href="#/guide/${esc(next.id)}">${esc(next.title)} ›</a>` : ""}
    </nav>
  </div>`;
}

async function fillExamples(main, g, e) {
  const list = main.querySelector(".g-examples");
  if (!list) return;
  const exs = g.examples[e.id] || [];
  const langs = [...new Set(exs.map((x) => x.lang))];
  try {
    const morphs = Object.fromEntries(await Promise.all(langs.map(async (l) => [l, await data.morph(l)])));
    await Promise.all(langs.map((l) => data.loadMeanings(l)));
    if (!main.contains(list)) return;
    list.innerHTML = exs.map((x) => exampleHTML(x, g, morphs[x.lang])).join("");
  } catch (err) {
    list.innerHTML = `<li class="muted">The examples couldn't load. Check your connection and open this page again.</li>`;
  }
}

/** #/guide/code/LANG/CODE: each part of a grammar label explained. */
async function codeHTML(g, asked, code) {
  // "auto" (from a search): whichever language's codes have it
  const [gm, hm] = await Promise.all([data.morph("grc"), data.morph("he")]);
  const inGreek = String(code).split("+").every((p) => gm[p]);
  const lang = asked === "he" || (asked === "auto" && !inGreek) ? "he" : "grc";
  const morph = lang === "grc" ? gm : hm;
  const l = codeLang(lang, code);
  const parts = lang === "grc" ? String(code).split("+") : String(code).replace(/^[HA]/, "").split("/").map((p) => String(code).charAt(0) + p);
  const known = parts.every((p) => morph[p]);
  const rows = parts.map((p) => {
    const m = morph[p];
    if (!m) return `<li><p>No grammar code ${esc(p)} is used in the Bible text here.</p></li>`;
    const label = lang === "grc" ? friendlyGrammar(m[0]) : heFriendlyGrammar(m[0]);
    const terms = labelTerms(label, l, g.table);
    return `<li class="g-code-part">
      <p class="g-code-label"><strong>${esc(label)}</strong></p>
      <ul class="rows g-terms">${terms.map((t) => {
        const e = t.id && g.byId[t.id];
        return e ? `<li><a class="row" href="#/guide/${esc(e.id)}"><span class="row-main"><span class="row-title">${esc(t.text)}</span>
          <span class="row-sub">${t.note ? esc(t.note.charAt(0).toUpperCase() + t.note.slice(1)) + "." : renderPlain(e.short, g)}</span></span>
          <span class="row-end">${linkText(e).toLowerCase() === t.text.toLowerCase() ? "" : `${esc(linkText(e))} `}›</span></a></li>`
          : `<li><span class="row"><span class="row-main"><span class="row-title">${esc(t.text)}</span></span></span></li>`;
      }).join("")}</ul>
      ${m[1] ? `<p class="g-code-desc">Put together: ${esc(m[1])}${/\p{L}/u.test(m[2] || "") ? `, as in “${esc(m[2])}”` : ""}.</p>` : ""}
    </li>`;
  });
  return `<div class="screen guide g-code">
    <p class="g-crumb"><a href="#/guide">Guide</a> › <a href="#/guide/grammar-labels">Grammar labels</a></p>
    ${head("What these words mean", lang === "grc" ? "A Greek word's grammar, part by part" : l === "arc" ? "An Aramaic word's grammar, part by part" : "A Hebrew word's grammar, part by part")}
    ${parts.length > 1 ? `<p>${lang === "grc" ? "This word is two words written as one" : "This word is made of parts: prefixes, the main word and endings"}. Each part has its own grammar.</p>` : ""}
    ${parts.length > 1 ? `<ol class="g-code-parts">${rows.join("")}</ol>` : `<ul class="g-code-parts single">${rows.join("")}</ul>`}
    ${known ? `<p class="g-code-raw muted">STEPBible's code for this: ${esc(code)}. The <a href="#/guide/grammar-labels">grammar labels</a> page explains where these come from, and <a href="#/guide/abbreviations">abbreviations</a> lists the short forms shown under words.</p>` : ""}
    <p><button type="button" class="btn secondary g-back">Back</button></p>
  </div>`;
}

function draw(main, g) {
  const box = main.querySelector(".g-results");
  const status = main.querySelector("[data-status]");
  const q = lastQuery.trim();
  main.querySelector(".g-sections").hidden = !!q;
  if (!q) { box.innerHTML = ""; status.textContent = ""; return; }
  const hits = searchGuide(q, g, ctxFor(g));
  const code = looksLikeCode(q) ? q : "";
  const codeRow = code ? `<li><a class="row" href="#/guide/code/auto/${encodeURIComponent(code)}"><span class="row-main">
    <span class="row-title">Explain the grammar code ${esc(code)}</span><span class="row-sub">Each part, one by one</span></span></a></li>` : "";
  box.innerHTML = hits.length || codeRow ? `<ul class="rows">${codeRow}${hits.slice(0, 40).map((h) => rowHTML(h.entry, g, h.why && h.why.toLowerCase() !== h.entry.title.toLowerCase() ? h.why : "")).join("")}</ul>`
    : `<p class="muted">Nothing in the guide matches “${esc(q)}”. Try a shorter word, or look the word up in the <a href="#/words">Words</a> tab.</p>`;
  status.textContent = `${hits.length} ${hits.length === 1 ? "match" : "matches"}`;
}

export const guideScreen = {
  title: "Guide",
  handlesTitle: true,
  async render(main, params) {
    main.innerHTML = `<div class="screen guide"><p class="muted">Loading the guide…</p></div>`;
    let g;
    try {
      g = await loadGuide();
    } catch (err) {
      main.innerHTML = `<div class="screen guide">${head("Guide")}<p>The guide couldn't load. Check your connection and try again.</p></div>`;
      document.title = "Guide · Aleph to Omega";
      return;
    }
    const [a, b, ...rest] = params;
    if (a === "code" && b) {
      const code = rest.join("/");
      main.innerHTML = await codeHTML(g, b === "he" || b === "auto" ? b : "grc", code);
      main.querySelector(".g-back").addEventListener("click", () => nav.goBack("#/guide"));
      document.title = `${code} · Guide · Aleph to Omega`;
      return;
    }
    if (a === "s" && g.sectionOf[b]) {
      main.innerHTML = sectionHTML(g, g.sectionOf[b]);
      document.title = `${g.sectionOf[b].title} · Guide · Aleph to Omega`;
      return;
    }
    if (a && g.byId[a]) {
      const e = g.byId[a];
      main.innerHTML = entryHTML(g, e);
      document.title = `${e.title} · Guide · Aleph to Omega`;
      fillExamples(main, g, e);
      return;
    }
    main.innerHTML = homeHTML(g);
    document.title = "Guide · Aleph to Omega";
    const input = main.querySelector("#guide-q");
    main.querySelector("form").addEventListener("submit", (ev) => { ev.preventDefault(); input.blur(); });
    input.addEventListener("input", () => { lastQuery = input.value; draw(main, g); });
    if (lastQuery) draw(main, g);
  },
};
