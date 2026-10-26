import * as store from "./store.js";
import { VERSES, verseForToday } from "./verses.js";
import { installTip, bindInstallTip } from "./install.js";

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const SETTINGS_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg>`;

function head(title, sub = "") {
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

function verseHTML(v) {
  const dir = v.lang === "he" ? "rtl" : "ltr";
  const words = v.words
    .map((w, i) => `<span class="w" role="button" tabindex="0" data-i="${i}" aria-pressed="${i === v.focus}">${esc(w.t)}</span>${w.p ? esc(w.p) : ""}`)
    .join(" ");
  return `<section class="verse" aria-labelledby="verse-ref">
    <p class="verse-ref" id="verse-ref">Verse for today · ${esc(v.ref)}</p>
    <p class="verse-original" lang="${v.lang}" dir="${dir}">${words}</p>
    <p class="verse-english">${esc(v.english)}</p>
    <div class="verse-gloss" aria-live="polite"></div>
  </section>
  <p class="verse-source">Tap any word to see what it means. Text: ${v.lang === "he" ? "Westminster Leningrad Codex" : "SBL Greek New Testament"}; English: Berean Standard Bible.</p>`;
}

function showGloss(root, v, i) {
  const w = v.words[i];
  root.querySelectorAll(".verse-original .w").forEach((el) => el.setAttribute("aria-pressed", String(Number(el.dataset.i) === i)));
  root.querySelector(".verse-gloss").innerHTML =
    `<span class="lemma" lang="${v.lang}">${esc(w.lemma)}</span>
     <span class="meaning">${esc(w.gloss)}</span>
     <span class="hint">${esc(w.parse)}</span>`;
}

export const today = {
  title: "Today",
  render(main) {
    let verse = verseForToday();
    const dateText = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
    main.innerHTML = `<div class="screen">
      ${head("Today", dateText)}
      ${installTip()}
      <div class="switch" role="group" aria-label="Verse language">
        ${VERSES.map((v) => `<button type="button" data-verse="${v.id}" aria-pressed="${v.id === verse.id}">${v.lang === "he" ? "Hebrew" : "Greek"}</button>`).join("")}
      </div>
      <div class="verse-slot">${verseHTML(verse)}</div>

      <h2>Start here</h2>
      <ul class="rows">
        <li><a class="row" href="#/media">
          <span class="row-glyph" lang="grc" aria-hidden="true">α</span>
          <span class="row-main"><span class="row-title">Watch Alpha with Angela</span><span class="row-sub">Hear Greek before you study it</span></span>
        </a></li>
        <li><a class="row" href="#/learn">
          <span class="row-glyph" aria-hidden="true">1</span>
          <span class="row-main"><span class="row-title">See your Greek learning path</span><span class="row-sub">Begins with the alphabet and its sounds</span></span>
        </a></li>
        <li><a class="row" href="#/review">
          <span class="row-glyph" aria-hidden="true">0</span>
          <span class="row-main"><span class="row-title">No reviews due</span><span class="row-sub">Words from your lessons will appear here</span></span>
        </a></li>
      </ul>
    </div>`;
    bindInstallTip(main);

    const slot = main.querySelector(".verse-slot");
    const bindVerse = () => {
      showGloss(slot, verse, verse.focus);
      slot.querySelectorAll(".verse-original .w").forEach((el) => {
        const pick = () => showGloss(slot, verse, Number(el.dataset.i));
        el.addEventListener("click", pick);
        el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      });
    };
    bindVerse();
    main.querySelectorAll("[data-verse]").forEach((b) =>
      b.addEventListener("click", () => {
        verse = VERSES.find((v) => v.id === b.dataset.verse);
        main.querySelectorAll("[data-verse]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        slot.innerHTML = verseHTML(verse);
        bindVerse();
      })
    );
  },
};

// ---------------------------------------------------------------- Learn

const PATHS = {
  grc: [
    ["The alphabet and its sounds", "24 letters, reading aloud, writing them"],
    ["Breathings, accents and punctuation", "The small marks above and around words"],
    ["Present verbs", "λύω, I loose: the endings that show who acts"],
    ["Second declension nouns", "λόγος, word: your first noun pattern"],
    ["The article and the cases", "ὁ, ἡ, τό, and what each case does in a sentence"],
    ["First declension nouns", "ἀρχή, beginning: the feminine pattern"],
  ],
  he: [
    ["The consonants", "22 letters, their sounds and final forms"],
    ["The vowels", "The dots and dashes added by the Masoretes"],
    ["Syllables and the shewa", "How words break up when read aloud"],
    ["Dagesh and other marks", "The dot that changes a letter's sound"],
    ["Nouns and the article", "הַ, the: making a noun definite"],
    ["Prepositions and “and”", "בְּ, לְ, כְּ and וְ joined to the next word"],
  ],
};

export const learn = {
  title: "Learn",
  render(main) {
    let lang = "grc";
    const draw = () => {
      main.querySelector(".path-slot").innerHTML = `
        <ol class="path" aria-label="${lang === "he" ? "Hebrew" : "Greek"} lessons">
          ${PATHS[lang].map(([t, s], i) => `<li class="${i === 0 ? "next" : ""}"><strong>${esc(t)}</strong><span>${esc(s)}</span></li>`).join("")}
        </ol>`;
    };
    main.innerHTML = `<div class="screen">
      ${head("Learn", "Step by step, from the alphabet to reading Scripture")}
      <div class="switch" role="group" aria-label="Language">
        <button type="button" data-lang="grc" aria-pressed="true">Greek</button>
        <button type="button" data-lang="he" aria-pressed="false">Hebrew</button>
      </div>
      <div class="note"><p>Lessons open here in Week 3 of the build. Until then, the videos are the best place to begin.</p></div>
      <div class="path-slot"></div>
      <p><a class="btn secondary" href="#/media">Go to the videos</a></p>
    </div>`;
    draw();
    main.querySelectorAll("[data-lang]").forEach((b) =>
      b.addEventListener("click", () => {
        lang = b.dataset.lang;
        main.querySelectorAll("[data-lang]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        draw();
      })
    );
  },
};

// ---------------------------------------------------------------- Read

export const read = {
  title: "Read",
  render(main) {
    main.innerHTML = `<div class="screen">
      ${head("Read", "Hebrew, Aramaic and Greek, word by word")}
      <div class="note">
        <p>The Reader arrives in the next update. You'll open any chapter in the original language, see the English meaning under every word, and read the Berean Standard Bible or the ESV alongside.</p>
        <p>For a taste, tap the words in today's verse.</p>
      </div>
      <p><a class="btn" href="#/today">Open today's verse</a></p>
    </div>`;
  },
};

// ---------------------------------------------------------------- Words

export const words = {
  title: "Words",
  render(main) {
    main.innerHTML = `<div class="screen">
      ${head("Words", "The dictionary for both languages")}
      <div class="note">
        <p>The dictionary arrives in Week 2. Search by English, Greek, Hebrew or Strong's number, and see every place a word appears.</p>
      </div>
    </div>`;
  },
};

// ---------------------------------------------------------------- Review

export const review = {
  title: "Review",
  render(main) {
    main.innerHTML = `<div class="screen">
      ${head("Review", "A few minutes a day keeps words from fading")}
      <div class="note">
        <p>Nothing to review yet. Words and forms from your lessons will appear here, timed so you see each one just before you'd forget it.</p>
      </div>
    </div>`;
  },
};

// ---------------------------------------------------------------- Media

const VIDEOS = [
  {
    lang: "grc",
    heading: "Greek",
    items: [
      { glyph: "α", title: "Alpha with Angela", sub: "Picture-based lessons taught entirely in Koine Greek", href: "https://freegreek.hismagnificence.com" },
    ],
  },
  {
    lang: "he",
    heading: "Hebrew",
    items: [
      { glyph: "א", title: "Aleph with Beth: introduction", sub: "A four-minute English welcome explaining the method", href: "https://www.youtube.com/watch?v=_rg-Dcfj-fc" },
      { glyph: "ב", title: "Aleph with Beth: lessons", sub: "The full course, taught in Biblical Hebrew", href: "https://www.youtube.com/playlist?list=PLq1vmb-z7PpQt2PDNUr7XOzBjWAOWf0Rt" },
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
    ${help ? `<p class="field-help">${help}</p>` : ""}
  </fieldset>`;
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
          "Erasmian keeps the vowels distinct, which helps with spelling. Restored Koine is closer to how the apostles spoke. Audio arrives in Week 3.")}
      </form>

      <h2>Backup</h2>
      <p class="muted" style="margin-top:0">Your progress is saved on this device only. Save a backup file now and then, and restore it on a new phone.</p>
      <div class="btn-row">
        <button type="button" class="btn" data-action="export">Save backup</button>
        <label class="btn secondary">Restore backup<input type="file" accept="application/json,.json" data-action="import" hidden></label>
      </div>

      <h2>About</h2>
      <p class="muted" style="margin-top:0">Aleph to Omega is a personal study app. Fonts: Gentium Plus and Noto Serif Hebrew (SIL Open Font Licence), Atkinson Hyperlegible (SIL Open Font Licence). Greek: SBL Greek New Testament (CC BY 4.0). Hebrew: Westminster Leningrad Codex (public domain). English: Berean Standard Bible (public domain).</p>
    </div>`;

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
