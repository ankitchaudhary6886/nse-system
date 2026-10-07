/*!
 * icons.js — declarative icon hydration.
 *
 * Any element carrying `data-icon="<lucide-name>"` gets the vendored Lucide SVG
 * prepended on load. Icons stay in the markup as a name (readable, greppable)
 * and the SVG body lives in vendor/lucide.js (compiled from lucide-static).
 *
 * Works with or without the markup having JS: if this module fails to load the
 * text label is still present, so nothing becomes an unlabelled mystery button.
 */
import { icon } from "/static/vendor/lucide.js";

function hydrate(root) {
  const nodes = (root || document).querySelectorAll("[data-icon]");
  nodes.forEach((el) => {
    if (el.dataset.iconDone === "1") return;
    const name = el.dataset.icon || "";
    const size = Number(el.dataset.iconSize || 16);
    const svg = icon(name, {
      size,
      class: el.dataset.iconClass || "fx-icon-sm",
    });
    if (!svg) {
      el.dataset.iconDone = "1";
      return;
    }
    el.insertAdjacentHTML("afterbegin", svg);
    el.dataset.iconDone = "1";
  });
}

function boot() {
  hydrate(document);
  /* Lists and panels re-render constantly; re-hydrate only newly added nodes. */
  const observer = new MutationObserver((records) => {
    let dirty = false;
    for (const record of records) {
      if (record.addedNodes && record.addedNodes.length) { dirty = true; break; }
    }
    if (dirty) hydrate(document);
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}

window.hydrateIcons = hydrate;
