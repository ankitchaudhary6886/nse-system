/* explainer.js - "click anything, understand it" layer.
 *
 * WHY: the owner is not a finance person. Every number and label on screen must
 * be answerable in ordinary words, on demand, without jargon.
 *
 * HOW TO USE: put `data-explain="regime"` on anything clickable. Keys come from
 * explain.py (GET /api/explain lists them). Nothing else is needed - this file
 * attaches one delegated listener, so elements added later are covered too.
 *
 * The text lives in explain.py, not here, so the terminal, the API and the
 * alerts can never disagree about what a word means.
 */
(function () {
  "use strict";

  var CACHE = {};
  var ORDER = ["what", "why", "look", "where", "when", "how", "sight"];

  function dialog() {
    return document.getElementById("dataDetailDialog");
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function render(key, payload) {
    var d = dialog();
    if (!d) return;
    var title = document.getElementById("dataDetailTitle");
    var body = document.getElementById("dataDetailBody");
    if (!title || !body) return;

    if (!payload || !payload.ok) {
      title.textContent = "Not explained yet";
      body.innerHTML =
        '<p class="ex-note">There is no stored explanation for <code>' +
        esc(key) + "</code> yet. Add it to <code>explain.py</code> and it will " +
        "appear here.</p>";
      if (d.showModal) { try { d.showModal(); } catch (e) {} }
      return;
    }

    var e = payload.entry;
    title.textContent = e.title || key;

    var labels = {};
    (payload.sections || []).forEach(function (s) { labels[s.key] = s.label; });

    var html = '<p class="ex-lead">' + esc(e.what) + "</p>";
    ORDER.forEach(function (k) {
      if (!e[k]) return;
      var cls = k === "sight" ? "ex-row ex-sight" : "ex-row";
      html += '<div class="' + cls + '">' +
        '<span class="ex-label">' + esc(labels[k] || k) + "</span>" +
        '<span class="ex-text">' + esc(e[k]) + "</span></div>";
    });
    html += '<p class="ex-foot">Explanations live in <code>explain.py</code> - ' +
      "one place, so every screen says the same thing.</p>";

    body.innerHTML = html;
    if (d.showModal) { try { d.showModal(); } catch (err) {} }
    d.setAttribute("data-explain-open", key);
  }

  function open(key) {
    if (!key) return;
    if (CACHE[key]) return render(key, CACHE[key]);
    fetch("/api/explain/" + encodeURIComponent(key), {
      credentials: "same-origin"
    })
      .then(function (r) { return r.json(); })
      .then(function (j) { CACHE[key] = j; render(key, j); })
      .catch(function () {
        render(key, { ok: false, key: key });
      });
  }

  /* One delegated listener covers every present and future element. */
  document.addEventListener("click", function (ev) {
    var el = ev.target.closest ? ev.target.closest("[data-explain]") : null;
    if (!el) return;
    /* Elements that also navigate keep navigating only if they say so. */
    if (el.hasAttribute("data-explain-only")) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    open(el.getAttribute("data-explain"));
  });

  /* Keyboard: Enter/Space on anything marked as an explain target. */
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    var el = ev.target.closest ? ev.target.closest("[data-explain]") : null;
    if (!el) return;
    if (el.tagName === "BUTTON" || el.tagName === "A") return; /* native */
    ev.preventDefault();
    open(el.getAttribute("data-explain"));
  });

  window.openExplain = open;
})();
