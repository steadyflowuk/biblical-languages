import * as store from "./store.js";
import * as screens from "./screens.js";
import { read, lxx, closeSheet } from "./reader.js";
import { words } from "./dictionary.js";
import { lesson } from "./lessons.js";
import { reviewScreen } from "./review.js";
import { alphabet } from "./alphabet.js";
import { bindAudio } from "./audio.js";
import * as nav from "./nav.js";

const ROUTES = {
  today: screens.today,
  learn: screens.learn,
  lesson,
  read,
  lxx,
  words,
  review: reviewScreen,
  alphabet,
  media: screens.media,
  settings: screens.settings,
};

store.applyDisplaySettings();
bindAudio();
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", store.applyDisplaySettings);

const main = document.getElementById("main");
let first = true;

let current = "";

function route() {
  // #/name or #/name/param/param… e.g. #/read/JHN/3/16
  const [name, ...params] = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const screen = ROUTES[name];
  if (!screen) {
    location.replace("#/today");
    return;
  }
  document.querySelectorAll(".tabs a[data-tab]").forEach((a) => {
    if (a.dataset.tab === (name === "lxx" ? "read" : name === "lesson" || name === "alphabet" ? "learn" : name)) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  nav.visited();
  const sameScreen = name === current;
  current = name;
  closeSheet();
  screen.render(main, params.map(decodeURIComponent));
  if (!screen.handlesTitle) document.title = `${screen.title} · Aleph to Omega`;
  if (!screen.handlesScroll) window.scrollTo(0, 0);
  if (!first && !sameScreen) main.focus({ preventScroll: true });
  first = false;
}

window.addEventListener("hashchange", route);
route();

// Offline support
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    // Check for a new version every time the app opens
    navigator.serviceWorker.register("sw.js", { updateViaCache: "none" }).then((reg) => reg.update()).catch(() => {
      /* offline support unavailable here (e.g. private browsing); the app still works online */
    });
  });
}
