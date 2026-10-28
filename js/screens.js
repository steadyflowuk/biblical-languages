import * as store from "./store.js";
import { VERSES as STARTER } from "./verses.js";
import * as data from "./data.js";
import { installTip, bindInstallTip } from "./install.js";
import * as esv from "./esv.js";
import * as lessons from "./lessons.js";
import * as review from "./review.js";
import { sayButton } from "./audio.js";

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const SETTINGS_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg>`;

export function head(title, sub = "") {
  return `<header class="screen-head">
    <div><h1>${esc(title)}</h1>${sub ? `<p>${esc(sub)}</p>` : ""}</div>
    ${title === "Settings" ? "" : `<a class="head-settings" href="#/settings" aria-label="Settings">${SETTINGS_ICON}</a>`}
  </header>`;
}

function toast(message) {
  document.querySelector(".toast")?.remove();
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  el.textContent = message;
  document.body.append(el);
  setTimeout(() => el.remove(), 3200);
}

// ---------------------------------------------------------------- Today

const SOURCE = {
  grc: "Greek: NA28 text from STEPBible (Tyndale House)",
  he: "Hebrew: Leningrad Codex from STEPBible (Tyndale House)",
};

function verseHTML(v) {
  const dir = v.lang === "he" ? "rtl" : "ltr";
  // Hebrew words joined by a maqaf (־) are written without a space between them
  const words = v.words
    .map((w, i) => `${w.pre ? esc(w.pre) : ""}<span class="w" role="button" tabindex="0" data-i="${i}" aria-pressed="${i === v.focus}">${esc(w.t)}</span>${w.p ? esc(String(w.p).replace(/[\u00b6\u00ac]/g, "")) : ""}`)
    .reduce((out, html, i) => out + (i && !String(v.words[i - 1].p || "").endsWith("\u05be") ? " " : "") + html, "");
  return `<section class="verse" aria-labelledby="verse-ref">
    <p class="verse-ref" id="verse-ref">Verse for today · ${esc(v.ref)}</p>
    <p class="verse-original" lang="${v.lang}" dir="${dir}">${words}</p>
    <p class="verse-english">${esc(v.english)}</p>
    <div class="verse-gloss" aria-live="polite"></div>
    ${/^[0-9A-Z]{3}-\d+-\d+$/.test(v.id) ? `<a class="verse-link" href="#/read/${v.id.replace(/-/g, "/")}">Read ${esc(v.ref.replace(/:\d+$/, ""))} word by word</a>` : ""}
  </section>
  <p class="verse-source">Tap any word to see what it means. ${SOURCE[v.lang]}; English: Berean Standard Bible.</p>`;
}

function showGloss(root, v, i) {
  const w = v.words[i];
  root.querySelectorAll(".verse-original .w").forEach((el) => el.setAttribute("aria-pressed", String(Number(el.dataset.i) === i)));
  root.querySelector(".verse-gloss").innerHTML =
    `<span class="lemma" lang="${v.lang}">${esc(w.lemma)}</span>${sayButton(w.lemma, v.lang, { className: "small" })}
     <span class="meaning">${esc(w.gloss)}</span>
     <span class="hint">${esc(w.parse)}</span>
     ${w.k ? `<a class="verse-link verse-dict" href="#/words/${encodeURIComponent(w.k)}">Look it up in the dictionary</a>` : ""}`;
}

export const today = {
  title: "Today",
  render(main) {
    // Show the built-in verses at once; swap in today's verses when the data arrives.
    let todays = { grc: STARTER.find((v) => v.lang === "grc"), he: STARTER.find((v) => v.lang === "he") };
    let lang = "grc";
    const dateText = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
    main.innerHTML = `<div class="screen">
      ${head("Today", dateText)}
      ${installTip()}
      <div class="switch" role="group" aria-label="Verse language">
        <button type="button" data-lang="grc" aria-pressed="true">Greek</button>
        <button type="button" data-lang="he" aria-pressed="false">Hebrew</button>
      </div>
      <div class="verse-slot"></div>

      <h2>Start here</h2>
      <ul class="rows">
        <li><a class="row" href="https://www.youtube.com/watch?v=gLe1GhR5l0E&list=PLO3VwXPRtV3yHbCsWoGCxEkBsDoXNkpMq&index=1" target="_blank" rel="noopener">
          <span class="row-glyph" lang="grc" aria-hidden="true">α</span>
          <span class="row-main"><span class="row-title">Watch Alpha with Angela, lesson 1</span><span class="row-sub">Hear Greek before you study it</span></span>
          <span class="row-end" aria-hidden="true">↗</span>
        </a></li>
        <li class="today-lesson"><a class="row" href="#/learn">
          <span class="row-glyph" aria-hidden="true">1</span>
          <span class="row-main"><span class="row-title">See your learning path</span><span class="row-sub">Lessons from the first letters to real verses</span></span>
        </a></li>
        <li class="today-review"><a class="row" href="#/review">
          <span class="row-glyph" aria-hidden="true">↻</span>
          <span class="row-main"><span class="row-title">Review your words</span><span class="row-sub">Flashcards that come back just before you'd forget</span></span>
        </a></li>
      </ul>
    </div>`;
    bindInstallTip(main);
    // how many words are waiting in Review today
    review.waitingCount().then((w) => {
      const li = main.querySelector(".today-review");
      if (!li) return;
      const any = Object.keys(store.get("cards") || {}).length || (store.get("reviewQueue") || []).length;
      const mins = Math.max(1, Math.round(w.total * 10 / 60));
      li.innerHTML = `<a class="row" href="#/review">
          <span class="row-glyph" aria-hidden="true">${w.total || "✓"}</span>
          <span class="row-main"><span class="row-title">${w.total ? `${w.total} ${w.total === 1 ? "word" : "words"} to review` : any ? "Reviews done for today" : "No words to review yet"}</span><span class="row-sub">${w.total ? `About ${mins} ${mins === 1 ? "minute" : "minutes"}` : any ? "Your words come back when they're due" : "Words from your lessons will appear here"}</span></span>
        </a>`;
    }).catch(() => { /* keep the plain link */ });
    // the next lesson in the language being learnt
    lessons.lessonIndex().then((index) => {
      const li = main.querySelector(".today-lesson");
      if (!li) return;
      const lang = store.get("learnLang") === "he" ? "he" : "grc";
      const next = lessons.nextLesson(index, lang);
      const p = next ? lessons.progressOf(next.id) || {} : {};
      li.innerHTML = next ? `<a class="row" href="#/lesson/${lang}/${next.id}">
          <span class="row-glyph" aria-hidden="true">${lang === "he" ? "א" : "α"}</span>
          <span class="row-main"><span class="row-title">${p.pos ? "Carry on" : "Next lesson"}: ${esc(next.title)}</span><span class="row-sub">${lessons.mixed(next.sub)}</span></span>
        </a>` : `<a class="row" href="#/learn">
          <span class="row-glyph" aria-hidden="true">✓</span>
          <span class="row-main"><span class="row-title">You've done every ${lang === "he" ? "Hebrew" : "Greek"} lesson so far</span><span class="row-sub">More lessons are on their way</span></span>
        </a>`;
    }).catch(() => { /* offline before the lessons were ever loaded: keep the link to Learn */ });

    const slot = main.querySelector(".verse-slot");
    const draw = () => {
      const verse = todays[lang];
      slot.innerHTML = verseHTML(verse);
      slot.dataset.verse = verse.id;
      showGloss(slot, verse, verse.focus);
      slot.querySelectorAll(".verse-original .w").forEach((el) => {
        const pick = () => showGloss(slot, verse, Number(el.dataset.i));
        el.addEventListener("click", pick);
        el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      });
    };
    draw();
    main.querySelectorAll("[data-lang]").forEach((b) =>
      b.addEventListener("click", () => {
        lang = b.dataset.lang;
        main.querySelectorAll("[data-lang]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        draw();
      })
    );
    data.verseOfTheDay()
      .then((verses) => {
        if (!main.contains(slot)) return; // the person has moved to another screen
        todays = data.pickForDay(verses);
        draw();
      })
      .catch(() => { /* offline before the data was ever loaded: keep the built-in verses */ });
  },
};

// ---------------------------------------------------------------- Learn

function pathHTML(index, lang) {
  const next = lessons.nextLesson(index, lang);
  const items = (index[lang] || []).map((e) => {
    const p = lessons.progressOf(e.id) || {};
    const n = String(e.id).split("-").pop();
    if (!e.file) {
      return `<li class="soon" data-n="${esc(n)}"><div class="path-item"><strong>${esc(e.title)}</strong><span>${lessons.mixed(e.sub)}</span>
        <em class="path-status">Coming soon</em></div></li>`;
    }
    const status = p.done ? `Done · ${p.best}% right first time · do it again`
      : p.pos ? "Carry on where you left off" : `Start${e.minutes ? ` · about ${e.minutes} minutes` : ""}`;
    const cls = p.done ? "done" : next && next.id === e.id ? "next" : "";
    return `<li class="${cls}" data-n="${p.done ? "✓" : esc(n)}"><a class="path-item" href="#/lesson/${lang}/${e.id}">
      <strong>${esc(e.title)}</strong><span>${lessons.mixed(e.sub)}</span><em class="path-status">${esc(status)}</em></a></li>`;
  });
  return `<ol class="path" aria-label="${lang === "he" ? "Hebrew" : "Greek"} lessons">${items.join("")}</ol>`;
}

export const learn = {
  title: "Learn",
  render(main) {
    let lang = store.get("learnLang") === "he" ? "he" : "grc";
    main.innerHTML = `<div class="screen">
      ${head("Learn", "Step by step, from the alphabet to reading Scripture")}
      <div class="switch" role="group" aria-label="Language">
        <button type="button" data-lang="grc" aria-pressed="${lang === "grc"}">Greek</button>
        <button type="button" data-lang="he" aria-pressed="${lang === "he"}">Hebrew</button>
      </div>
      <p class="muted learn-how">Each lesson has five steps: hear and see, notice, practise, read real verses, then add the new words to your review list.</p>
      <ul class="rows learn-abc"><li><a class="row" href="#/alphabet/${lang}">
        <span class="row-glyph" aria-hidden="true">${lang === "he" ? "א" : "α"}</span>
        <span class="row-main"><span class="row-title">Alphabet and sounds</span><span class="row-sub">Every letter, the marks that change a sound, and verses to read aloud</span></span>
      </a></li></ul>
      <div class="path-slot"><p class="muted">Loading the lessons…</p></div>
      <p><a class="btn secondary" href="#/media">Videos to watch alongside</a></p>
    </div>`;
    const slot = main.querySelector(".path-slot");
    let index = null;
    const draw = () => { if (index) slot.innerHTML = pathHTML(index, lang); };
    const load = () => lessons.lessonIndex().then((ix) => { index = ix; if (main.contains(slot)) draw(); }).catch(() => {
      if (!main.contains(slot)) return;
      slot.innerHTML = `<div class="note"><p>The lessons couldn't load. Check you're connected to the internet.</p>
        <p><button type="button" class="btn secondary" data-retry>Try again</button></p></div>`;
      slot.querySelector("[data-retry]").addEventListener("click", load);
    });
    load();
    main.querySelectorAll("[data-lang]").forEach((b) =>
      b.addEventListener("click", () => {
        lang = b.dataset.lang;
        store.set("learnLang", lang);
        const abc = main.querySelector(".learn-abc a");
        abc.setAttribute("href", `#/alphabet/${lang}`);
        abc.querySelector(".row-glyph").textContent = lang === "he" ? "א" : "α";
        main.querySelectorAll("[data-lang]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        draw();
      })
    );
  },
};

// ---------------------------------------------------------------- Media

const VIDEOS = [
  {
    lang: "grc",
    heading: "Greek",
    items: [
      { glyph: "α", title: "Alpha with Angela: lesson 1", sub: "Picture-based lessons taught entirely in Koine Greek, with the same pronunciation as this app", href: "https://www.youtube.com/watch?v=gLe1GhR5l0E&list=PLO3VwXPRtV3yHbCsWoGCxEkBsDoXNkpMq&index=1" },
      { glyph: "β", title: "Alpha with Angela: course website", sub: "How the course works, downloads and the pronunciation guide", href: "https://freegreek.online/" },
    ],
  },
  {
    lang: "he",
    heading: "Hebrew",
    items: [
      { glyph: "א", title: "Aleph with Beth: introduction", sub: "A four-minute English welcome explaining the method", href: "https://www.youtube.com/watch?v=_rg-Dcfj-fc" },
      { glyph: "ב", title: "Aleph with Beth: lessons 1 to 50", sub: "The course in order, taught in Biblical Hebrew", href: "https://www.youtube.com/watch?v=y640-FIpxQs&list=PLq1vmb-z7PpQt2PDNUr7XOzBjWAOWf0Rt" },
    ],
  },
];

export const media = {
  title: "Videos",
  render(main) {
    main.innerHTML = `<div class="screen">
      ${head("Videos", "Hear the languages before you study them")}
      ${VIDEOS.map((g) => `
        <h2>${g.heading}</h2>
        <ul class="rows">
          ${g.items.map((it) => `<li><a class="row" href="${it.href}" target="_blank" rel="noopener">
            <span class="row-glyph" lang="${g.lang}" aria-hidden="true">${it.glyph}</span>
            <span class="row-main"><span class="row-title">${esc(it.title)}</span><span class="row-sub">${esc(it.sub)}</span></span>
            <span class="row-end" aria-hidden="true">↗</span>
          </a></li>`).join("")}
        </ul>`).join("")}
      <p class="muted" style="margin-top:20px">More channels for each level, including children's songs for Hebrew sounds, arrive in Week 4. Links open YouTube or the course website.</p>
    </div>`;
  },
};

// ---------------------------------------------------------------- Settings

function radios(name, legend, options, current, help = "") {
  return `<fieldset>
    <legend>${legend}</legend>
    <div class="choices">
      ${options.map(([value, label]) => `<label><input type="radio" name="${name}" value="${value}" ${value === current ? "checked" : ""}> ${label}</label>`).join("")}
    </div>
    ${help ? `<p class="field-help">${lessons.mixed(help)}</p>` : ""}
  </fieldset>`;
}

// ---- ESV key (kept on this device only; never in backups)

function esvSettingsHTML() {
  if (esv.hasKey()) {
    return `<p class="esv-ok">ESV key saved on this device. Turn on the ESV in the Reader's display options.</p>
      <p class="muted">The key isn't included in backups, so add it again on each device.</p>
      <div class="btn-row"><button type="button" class="btn secondary" data-esv-remove>Remove key</button></div>`;
  }
  return `<p class="muted" style="margin-top:0">The ESV can appear alongside the Berean Standard Bible. It needs a free key from Crossway, which stays on this device and isn't included in backups.</p>
    <ol class="steps muted">
      <li>Sign up at api.esv.org (the button below opens it) and create an application for personal use.</li>
      <li>Copy its key, a long code of letters and numbers.</li>
      <li>Paste it below and choose “Save key”.</li>
    </ol>
    <p><a class="btn secondary" href="https://api.esv.org/" target="_blank" rel="noopener">Open api.esv.org</a></p>
    <label class="field"><span>ESV key</span>
      <input type="text" data-esv-key autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Paste your key here"></label>
    <div class="btn-row"><button type="button" class="btn" data-esv-save>Save key</button></div>
    <p class="field-help" data-esv-msg role="status"></p>`;
}

function wireEsvSettings(box) {
  box.querySelector("[data-esv-remove]")?.addEventListener("click", () => {
    esv.clearKey();
    box.innerHTML = esvSettingsHTML();
    wireEsvSettings(box);
    toast("ESV key removed from this device");
  });
  box.querySelector("[data-esv-save]")?.addEventListener("click", async () => {
    const input = box.querySelector("[data-esv-key]");
    const msg = box.querySelector("[data-esv-msg]");
    const key = String(input.value || "").replace(/^\s*(authorization:\s*)?token\s+/i, "").trim();
    if (!key) { msg.textContent = "Paste your key first."; input.focus(); return; }
    msg.textContent = "Checking the key…";
    const result = await esv.testKey(key);
    if (!result.ok) { msg.textContent = result.message; return; }
    esv.setKey(key);
    box.innerHTML = esvSettingsHTML();
    wireEsvSettings(box);
    toast("ESV key saved");
  });
}

export const settings = {
  title: "Settings",
  render(main) {
    main.innerHTML = `<div class="screen">
      ${head("Settings")}
      <form class="settings" onsubmit="return false">
        ${radios("textSize", "Text size", [["normal", "Standard"], ["large", "Large"], ["larger", "Larger"], ["largest", "Largest"]], store.get("textSize"))}
        ${radios("theme", "Appearance", [["auto", "Match device"], ["light", "Light"], ["dark", "Dark"]], store.get("theme"))}
        ${radios("greekVoice", "Greek pronunciation", [["erasmian", "Erasmian (taught in most colleges)"], ["koine", "Restored Koine (first-century sounds)"]], store.get("greekVoice"),
          "Erasmian keeps the vowels distinct, which helps with spelling. Restored Koine is closer to how the apostles spoke: ει sounds like “ee”, αι like the e in “bet”, β like v, and δ like the th in “this”. The lessons write pronunciations the Erasmian way, and Listen buttons follow this choice.")}
        ${radios("speechRate", "Listening speed", [["slow", "Slow"], ["normal", "Normal"]], store.get("speechRate"),
          "Listen buttons use your phone's own Greek and Hebrew voices. For Erasmian, the Modern Greek voice is given each word respelt so it comes out the Erasmian way; it's close, not perfect. Hebrew uses the Israeli voice, and the divine name is read Adonai. On an iPhone, the voices follow the ringer switch: on silent, you won't hear them.")}
        <div class="btn-row say-test">${sayButton("ἐν ἀρχῇ ἦν ὁ λόγος", "grc", { label: "Try Greek" })}${sayButton("בְּרֵאשִׁית בָּרָא אֱלֹהִים", "he", { label: "Try Hebrew" })}</div>
      </form>

      <h2>English Standard Version (ESV)</h2>
      <div class="esv-settings">${esvSettingsHTML()}</div>

      <h2>Backup</h2>
      <p class="muted" style="margin-top:0">Your progress is saved on this device only. Save a backup file now and then, and restore it on a new phone.</p>
      <div class="btn-row">
        <button type="button" class="btn" data-action="export">Save backup</button>
        <label class="btn secondary">Restore backup<input type="file" accept="application/json,.json" data-action="import" hidden></label>
      </div>

      <h2>About</h2>
      <p class="muted" style="margin-top:0">Aleph to Omega is a personal study app.</p>
      <p class="muted">Greek New Testament (NA28 text), Hebrew and Aramaic Old Testament (Leningrad Codex), word-by-word translations, grammar and lexicons: STEPBible Data, created by STEPBible.org based on work at Tyndale House Cambridge, licensed CC BY 4.0, reformatted for this app. Dictionary definitions draw on Abbott-Smith's Manual Greek Lexicon of the New Testament, the Liddell–Scott lexicon and Brown–Driver–Briggs, as included in STEPBible's lexicons. English: Berean Standard Bible, public domain. Septuagint: H. B. Swete's edition (1909–1930), public domain, from the LXX-Swete-1930 database by Eliran Wong (GPL-3.0); lined up with the Hebrew verses using STEPBible's versification data (CC BY 4.0). Fonts: Gentium Plus, Noto Serif Hebrew and Atkinson Hyperlegible, SIL Open Font Licence. Review scheduling: ts-fsrs by Open Spaced Repetition, MIT licence. Listen buttons use your device's own voices.</p>
    </div>`;

    main.querySelector(".screen").insertAdjacentHTML("beforeend", `<div class="esv-notice"><p class="muted">${esc(esv.NOTICE)}</p><p><a class="btn secondary" href="https://www.esv.org" target="_blank" rel="noopener">Visit www.esv.org</a></p></div>`);
    wireEsvSettings(main.querySelector(".esv-settings"));

    main.querySelector(".settings").addEventListener("change", (e) => {
      const input = e.target;
      if (input.type !== "radio") return;
      store.set(input.name, input.value);
      store.applyDisplaySettings();
    });

    main.querySelector('[data-action="export"]').addEventListener("click", async () => {
      const name = `aleph-to-omega-backup-${new Date().toISOString().slice(0, 10)}.json`;
      const json = JSON.stringify(store.exportBackup(), null, 2);
      // iPhone/iPad home-screen apps can't download files, so use the share sheet ("Save to Files") there.
      const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
      const file = typeof File === "function" ? new File([json], name, { type: "application/json" }) : null;
      if (standalone && file && navigator.canShare?.({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title: "Aleph to Omega backup" });
          toast("Backup saved");
        } catch (err) {
          if (err.name !== "AbortError") toast("The backup couldn't be shared. Try again from Safari.");
        }
        return;
      }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([json], { type: "application/json" }));
      a.download = name;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      toast("Backup saved");
    });

    main.querySelector('[data-action="import"]').addEventListener("change", async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      try {
        const count = store.importBackup(JSON.parse(await file.text()));
        store.applyDisplaySettings();
        toast(`Backup restored (${count} items)`);
        settings.render(main);
      } catch (err) {
        toast(err instanceof SyntaxError || !err.message ? "That file couldn't be read. Choose a backup saved from this app." : err.message);
      }
    });
  },
};
