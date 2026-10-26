// "Add to Home Screen" help. Android/Chrome offers a real install prompt;
// iPhone and iPad need the Share menu, so we explain that instead.
import * as store from "./store.js";

let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
  document.querySelectorAll("[data-install]").forEach((b) => (b.hidden = false));
});

const isStandalone = () =>
  matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

const isIOS = () =>
  /iphone|ipad|ipod/i.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

export function installTip() {
  if (isStandalone() || store.get("installTipDismissed")) return "";
  const text = isIOS()
    ? "Put this app on your home screen: tap the Share button, then <strong>Add to Home Screen</strong>. It then opens full screen and works offline."
    : "Put this app on your home screen so it opens full screen and works offline.";
  return `<aside class="install-tip" aria-label="Install the app">
    <img src="assets/icons/icon-192.png" alt="">
    <div>
      <p>${text}</p>
      ${isIOS() ? "" : `<p style="margin-top:10px"><button type="button" class="btn" data-install ${deferredPrompt ? "" : "hidden"}>Install app</button></p>`}
    </div>
    <button type="button" class="close" aria-label="Dismiss" data-dismiss-install>×</button>
  </aside>`;
}

export function bindInstallTip(root) {
  root.querySelector("[data-dismiss-install]")?.addEventListener("click", () => {
    store.set("installTipDismissed", true);
    root.querySelector(".install-tip")?.remove();
  });
  root.querySelector("[data-install]")?.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    root.querySelector(".install-tip")?.remove();
  });
}
