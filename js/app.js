import * as store from "./store.js";
import * as screens from "./screens.js";

const ROUTES = {
  today: screens.today,
  learn: screens.learn,
  read: screens.read,
  words: screens.words,
  review: screens.review,
  media: screens.media,
  settings: screens.settings,
};

store.applyDisplaySettings();
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", store.applyDisplaySettings);

const main = document.getElementById("main");
let first = true;

function route() {
  const name = (location.hash.match(/^#\/([a-z]+)/) || [])[1];
  const screen = ROUTES[name];
  if (!screen) {
    location.replace("#/today");
    return;
  }
  document.querySelectorAll(".tabs a[data-tab]").forEach((a) => {
    if (a.dataset.tab === name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  screen.render(main);
  document.title = `${screen.title} · Aleph to Omega`;
  window.scrollTo(0, 0);
  if (!first) main.focus({ preventScroll: true });
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
