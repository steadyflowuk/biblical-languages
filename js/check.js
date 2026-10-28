// Check this device (Session 12, route #/check, from Settings): what this phone or tablet supports, whether the app is
// saved for offline use, its voices (with a test you can hear), fonts and storage — and a plain-text report to send.
import * as store from "./store.js";
import { head } from "./screens.js";
import { speak, voiceFor, canSpeak, stopSpeaking } from "./sound.js";
import { streak } from "./activity.js";
import { whenText } from "./progress.js";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const YES = "✓";
const NO = "✗";

// ---------------------------------------------------------------- facts about the device

/** "iPhone · iOS 17.1 · Safari" from the browser's description of itself. */
export function describeDevice(ua, touchPoints) {
  const u = ua || "";
  let device = "Computer";
  let system = "";
  let browser = "";
  const ios = u.match(/(?:iPhone|iPad|iPod).*? OS (\d+)[_.](\d+)/);
  const ipadDesktop = /Macintosh/.test(u) && touchPoints > 1; // iPadOS asks for desktop sites by default
  if (ios || ipadDesktop) {
    device = /iPad/.test(u) || ipadDesktop ? "iPad" : /iPod/.test(u) ? "iPod" : "iPhone";
    const v = ios ? `${ios[1]}.${ios[2]}` : ((u.match(/Version\/(\d+\.\d+)/) || [])[1] || "");
    system = v ? `${device === "iPad" ? "iPadOS" : "iOS"} ${v}` : "iOS";
    browser = /CriOS/.test(u) ? "Chrome" : /FxiOS/.test(u) ? "Firefox" : /EdgiOS/.test(u) ? "Edge" : "Safari";
  } else if (/Android/.test(u)) {
    device = /Mobile/.test(u) ? "Android phone" : "Android tablet";
    system = `Android ${(u.match(/Android (\d+(?:\.\d+)?)/) || [])[1] || ""}`.trim();
    const sam = u.match(/SamsungBrowser\/(\d+)/);
    const ch = u.match(/Chrome\/(\d+)/);
    browser = sam ? `Samsung Internet ${sam[1]}` : /Firefox\//.test(u) ? "Firefox" : ch ? `Chrome ${ch[1]}` : "browser";
  } else {
    system = /Mac OS X/.test(u) ? "macOS" : /Windows/.test(u) ? "Windows" : /Linux/.test(u) ? "Linux" : "";
    const ch = u.match(/(?:Chrome|Chromium)\/(\d+)/);
    browser = /Edg\//.test(u) ? "Edge" : ch ? `Chrome ${ch[1]}` : /Firefox\/(\d+)/.test(u) ? "Firefox" : /Safari\//.test(u) ? "Safari" : "browser";
  }
  return { device, system, browser, apple: !!(ios || ipadDesktop), android: /Android/.test(u) };
}

const supports = (prop, value) => { try { return !!(window.CSS && CSS.supports(prop, value)); } catch (e) { return false; } };
const supportsSelector = (sel) => { try { return !!(window.CSS && CSS.supports(`selector(${sel})`)); } catch (e) { return false; } };

/** Flex gap can't be asked about directly: measure it. */
function flexGap() {
  const box = document.createElement("div");
  box.style.cssText = "display:flex;flex-direction:column;gap:1px;position:absolute;visibility:hidden";
  box.appendChild(document.createElement("div"));
  box.appendChild(document.createElement("div"));
  document.body.appendChild(box);
  const ok = box.scrollHeight === 1;
  box.remove();
  return ok;
}

/** Layout features the app uses, with the iOS version that brought each; missing ones only change the look. */
export function features() {
  return [
    { name: "Spacing between buttons and rows", ok: flexGap(), since: "iOS 14.1" },
    { name: "Soft highlight colours", ok: supports("color", "color-mix(in srgb, red 50%, blue)"), since: "iOS 16.2", cosmetic: true },
    { name: "Ticked answer outlined", ok: supportsSelector(":has(*)"), since: "iOS 15.4", cosmetic: true },
    { name: "Keyboard focus outline", ok: supportsSelector(":focus-visible"), since: "iOS 15.4", cosmetic: true },
    { name: "Page behind a pop-up kept still", ok: "inert" in HTMLElement.prototype, since: "iOS 15.5", cosmetic: true },
  ];
}

async function offlineState() {
  const out = { worker: false, version: "", shellFiles: 0, books: 0, dataFiles: 0 };
  try {
    out.worker = !!(navigator.serviceWorker && navigator.serviceWorker.controller);
    if (!window.caches) return out;
    const keys = await caches.keys();
    const shell = keys.filter((k) => k.indexOf("shell-") === 0).sort().pop();
    if (shell) {
      out.version = shell.slice(6);
      out.shellFiles = (await (await caches.open(shell)).keys()).length;
    }
    if (keys.indexOf("data-v1") >= 0) {
      const reqs = await (await caches.open("data-v1")).keys();
      out.dataFiles = reqs.length;
      out.books = reqs.filter((r) => /\/data\/(gnt|hot)\/[0-9A-Z]{3}\.json/.test(r.url)).length;
    }
  } catch (e) { /* caches unavailable (private browsing) */ }
  return out;
}

async function storageState() {
  const out = { local: false, persisted: null, used: null, quota: null };
  try { localStorage.setItem("ao:check", "1"); localStorage.removeItem("ao:check"); out.local = true; } catch (e) { /* blocked */ }
  try {
    if (navigator.storage && navigator.storage.persisted) out.persisted = await navigator.storage.persisted();
    if (navigator.storage && navigator.storage.estimate) {
      const e = await navigator.storage.estimate();
      out.used = e.usage;
      out.quota = e.quota;
    }
  } catch (e) { /* not offered */ }
  return out;
}

function fontState() {
  const f = document.fonts;
  if (!f || !f.check) return null;
  return {
    english: f.check('16px "Atkinson"'),
    greek: f.check('16px "Gentium"', "λόγος"),
    hebrew: f.check('16px "Hebrew Serif"', "שָׁלוֹם"),
  };
}

/** The phone's voices, waiting a moment for them to be listed (they arrive late on some phones). */
function voices() {
  return new Promise((resolve) => {
    if (!canSpeak()) { resolve(null); return; }
    const pick = () => ({ grc: voiceFor("grc"), he: voiceFor("he"), count: (speechSynthesis.getVoices() || []).length });
    const now = pick();
    if (now.count) { resolve(now); return; }
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(pick()); } };
    try { speechSynthesis.addEventListener("voiceschanged", finish); } catch (e) { /* older engines */ }
    setTimeout(finish, 2000);
  });
}

const mb = (n) => (n == null ? "" : n < 1e6 ? `${Math.max(1, Math.round(n / 1e3))} KB` : n < 1e9 ? `${Math.round(n / 1e6)} MB` : `${(n / 1e9).toFixed(1)} GB`);
const SAMPLE = { grc: "ἐν ἀρχῇ ἦν ὁ λόγος", he: "בְּרֵאשִׁית בָּרָא אֱלֹהִים" };
const LANG = { grc: "Greek", he: "Hebrew" };
const SIZE = { normal: "standard", large: "large", larger: "larger", largest: "largest" };
const THEME = { auto: "match device", light: "light", dark: "dark" };

// ---------------------------------------------------------------- the screen

export const check = {
  title: "Check this device",
  async render(main) {
    const d = describeDevice(navigator.userAgent, navigator.maxTouchPoints || 0);
    const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
    const sound = { grc: { started: null, heard: null }, he: { started: null, heard: null } };
    main.innerHTML = `<div class="screen ck">
      ${head("Check this device", "For a new phone or tablet, or when something doesn't work")}
      <p>This looks at what your ${esc(d.device === "Computer" ? "computer" : d.device)} can do, and tests the voices. Nothing is sent anywhere: at the end you can copy or share the report yourself.</p>
      <div class="ck-body"><p class="muted">Checking…</p></div>
    </div>`;
    const [off, st, vs] = await Promise.all([offlineState(), storageState(), voices()]);
    const fonts = fontState();
    const feats = features();
    const body = main.querySelector(".ck-body");
    if (!body) return;

    const row = (ok, title, detail, tag) => `<${tag || "li"} class="ck-row ${ok === true ? "ok" : ok === false ? "bad" : "info"}">
        <span class="ck-mark" aria-hidden="true">${ok === true ? YES : ok === false ? "!" : "•"}</span>
        <span class="ck-text"><strong>${title}</strong>${detail ? `<span>${detail}</span>` : ""}</span></${tag || "li"}>`;
    const missing = feats.filter((f) => !f.ok);
    const appleUpdate = d.apple ? "Updating iOS (Settings › General › Software Update) brings these in." : "Updating the browser brings these in.";

    const voiceRow = (l) => {
      const v = vs && vs[l];
      const name = v ? `${esc(v.name)} (${esc(v.lang)})` : "";
      return `<li class="ck-voice" data-lang="${l}">
          ${row(vs === null ? false : v ? true : vs.count ? false : null, `${LANG[l]} voice`,
            vs === null ? "This browser can't speak aloud."
              : v ? name
              : vs.count ? `None installed. ${d.apple ? `Settings › Accessibility › Spoken Content › Voices › ${LANG[l]}` : "Settings › search “Text-to-speech” › install the voice data"}.`
              : "The phone didn't list its voices; the test below will tell.", "div")}
          <div class="ck-test">
            <button type="button" class="btn secondary" data-test="${l}">Play the ${LANG[l]} test</button>
            <span class="ck-said muted" lang="${l === "he" ? "he" : "grc"}"${l === "he" ? ' dir="rtl"' : ""}>${SAMPLE[l]}</span>
          </div>
          <div class="ck-heard" hidden>
            <p class="ck-q">Did you hear it?</p>
            <p class="btn-row"><button type="button" class="btn secondary" data-heard="${l}" data-v="yes">Yes</button>
              <button type="button" class="btn secondary" data-heard="${l}" data-v="no">No</button></p>
            <p class="ck-tip muted" hidden>${d.apple ? "Check the ringer switch on the side isn't on silent, and the volume is up. If it's still quiet, add the voice as above." : "Check the volume is up. If it's still quiet, install the voice data as above."}</p>
          </div>
        </li>`;
    };

    body.innerHTML = `
      <section><h2>This device</h2><ul class="ck-list">
        ${row(null, `${esc(d.device)}${d.system ? ` · ${esc(d.system)}` : ""}`, esc(d.browser))}
        ${row(standalone, standalone ? "Opened from the home screen" : "Opened in the browser", standalone ? "" : "For the full app, add it to your home screen (see Today).")}
        ${row(navigator.onLine, navigator.onLine ? "Online" : "Offline", "")}
      </ul></section>

      <section><h2>Working offline</h2><ul class="ck-list">
        ${row(off.worker && off.shellFiles > 0, off.worker && off.shellFiles ? "The app is saved on this device" : "The app isn't saved for offline use yet",
          off.worker && off.shellFiles ? `Version ${esc(off.version)} · ${off.shellFiles} files` : "Open the app once while online, then close and reopen it.")}
        ${row(null, `${off.books} Bible ${off.books === 1 ? "book" : "books"} saved for reading offline`, "Books are saved as you open them in Read.")}
        ${row(st.local, st.local ? "Your progress can be saved" : "Your progress can't be saved here", st.local ? (st.persisted ? "The device has agreed to keep it." : "Save a backup now and then (Progress › Backup).") : "Private browsing blocks saving. Open the app normally.")}
        ${st.used != null ? row(null, `Space used: ${mb(st.used)}`, st.quota ? `of ${mb(st.quota)} allowed` : "") : ""}
      </ul></section>

      <section><h2>Voices</h2><ul class="ck-list">${voiceRow("grc")}${voiceRow("he")}</ul></section>

      <section><h2>Letters and layout</h2><ul class="ck-list">
        ${fonts ? row(fonts.english && fonts.greek && fonts.hebrew, fonts.english && fonts.greek && fonts.hebrew ? "The app's fonts are in use" : "Some fonts haven't loaded",
          `English ${fonts.english ? YES : NO} · Greek <span lang="grc">λόγος</span> ${fonts.greek ? YES : NO} · Hebrew <span lang="he">שָׁלוֹם</span> ${fonts.hebrew ? YES : NO}`) : ""}
        ${missing.length ? row(missing.some((f) => !f.cosmetic) ? false : null, `${missing.length} small ${missing.length === 1 ? "difference" : "differences"} in how things look`,
          `${missing.map((f) => `${esc(f.name)}${f.since ? ` (${f.since})` : ""}`).join("; ")}. ${appleUpdate}`)
          : row(true, "Everything displays as designed", "")}
        ${row(null, `Screen ${Math.round(screen.width)} × ${Math.round(screen.height)}`, `Text size: ${esc(SIZE[store.get("textSize")] || store.get("textSize"))} · Appearance: ${esc(THEME[store.get("theme")] || store.get("theme"))}`)}
      </ul></section>

      <section><h2>Report</h2>
        <p>Copy or share this to send it on, for example to whoever looks after the app.</p>
        <pre class="ck-report" tabindex="0"></pre>
        <p class="btn-row"><button type="button" class="btn" data-copy>Copy the report</button>
          ${navigator.share ? `<button type="button" class="btn secondary" data-share>Share the report</button>` : ""}</p>
      </section>`;

    const report = () => {
      const cards = Object.keys(store.get("cards") || {}).length;
      const lessonsDone = Object.values(store.get("lessons") || {}).filter((p) => p && p.done).length;
      const lines = [
        `Aleph to Omega device check — ${new Date().toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}`,
        `App version: ${off.version || "not saved"}${off.worker ? "" : " (offline helper not running)"}`,
        `Device: ${d.device}${d.system ? ` · ${d.system}` : ""} · ${d.browser} · ${standalone ? "home-screen app" : "in the browser"}`,
        `Screen: ${Math.round(screen.width)}×${Math.round(screen.height)} @${window.devicePixelRatio || 1}x · text ${store.get("textSize")} · theme ${store.get("theme")}`,
        `Online: ${navigator.onLine ? "yes" : "no"} · offline files: ${off.shellFiles} · Bible books saved: ${off.books} · data files: ${off.dataFiles}`,
        `Storage: ${st.local ? "works" : "BLOCKED"}${st.persisted === true ? " · kept" : st.persisted === false ? " · not guaranteed" : ""}${st.used != null ? ` · used ${mb(st.used)}${st.quota ? ` of ${mb(st.quota)}` : ""}` : ""}`,
        `Fonts: ${fonts ? `English ${fonts.english ? YES : NO} Greek ${fonts.greek ? YES : NO} Hebrew ${fonts.hebrew ? YES : NO}` : "can't tell"}`,
        `Layout: ${missing.length ? missing.map((f) => `${f.name} ${NO}`).join("; ") : "all features"}`,
        `Voices listed: ${vs === null ? "no speech" : vs.count} · Greek: ${vs && vs.grc ? `${vs.grc.name} (${vs.grc.lang})` : "none"} · Hebrew: ${vs && vs.he ? `${vs.he.name} (${vs.he.lang})` : "none"}`,
        ...["grc", "he"].map((l) => `${LANG[l]} test: ${sound[l].started === null ? "not played" : sound[l].started ? "started" : "DID NOT START"}${sound[l].heard ? ` · heard: ${sound[l].heard}` : ""}`),
        `Settings: Greek ${store.get("greekVoice")} · speed ${store.get("speechRate")} · learning ${store.get("learnLang")}`,
        `Progress: ${lessonsDone} lessons done · ${cards} review cards · ${streak().current} days in a row · last backup ${store.get("lastBackup") ? whenText(store.get("lastBackup")) : "never"}`,
        `Browser: ${navigator.userAgent}`,
      ];
      return lines.join("\n");
    };
    const pre = body.querySelector(".ck-report");
    const redraw = () => { pre.textContent = report(); };
    redraw();

    body.querySelectorAll("[data-test]").forEach((b) => b.addEventListener("click", () => {
      const l = b.dataset.test;
      const li = b.closest(".ck-voice");
      sound[l] = { started: false, heard: null };
      // speak at once, inside the tap (phones refuse speech started later)
      const r = speak(SAMPLE[l], {
        lang: l, greekVoice: store.get("greekVoice"), rate: store.get("speechRate"),
        onstart: () => { sound[l].started = true; redraw(); },
        onfail: () => { redraw(); },
      });
      if (!r.ok) sound[l].started = false;
      li.querySelector(".ck-heard").hidden = false;
      redraw();
    }));
    body.querySelectorAll("[data-heard]").forEach((b) => b.addEventListener("click", () => {
      const l = b.dataset.heard;
      sound[l].heard = b.dataset.v;
      const li = b.closest(".ck-voice");
      li.querySelectorAll("[data-heard]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      li.querySelector(".ck-tip").hidden = b.dataset.v !== "no";
      redraw();
    }));
    const done = (msg) => {
      document.querySelector(".toast") && document.querySelector(".toast").remove();
      const el = document.createElement("div");
      el.className = "toast";
      el.setAttribute("role", "status");
      el.textContent = msg;
      document.body.append(el);
      setTimeout(() => el.remove(), 3200);
    };
    body.querySelector("[data-copy]").addEventListener("click", async () => {
      const text = report();
      try {
        await navigator.clipboard.writeText(text);
        done("Report copied");
      } catch (e) {
        // older phones: select the text so it can be copied by hand
        const range = document.createRange();
        range.selectNodeContents(pre);
        const sel = getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        done("Press and hold the selected text to copy it");
      }
    });
    const share = body.querySelector("[data-share]");
    if (share) share.addEventListener("click", () => {
      navigator.share({ title: "Aleph to Omega device check", text: report() }).catch(() => { /* cancelled */ });
    });
    window.addEventListener("hashchange", stopSpeaking, { once: true });
  },
};
