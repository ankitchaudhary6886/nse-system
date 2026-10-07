/* ideals.js - "actual vs ideal" everywhere, automatically.
 *
 * WHY: a number on its own means nothing to someone who is not a finance
 * person. "ROCE 8.1" says nothing. "8.1% - below the 15% we look for" says
 * everything.
 *
 * HOW IT WORKS: ideal.py holds the bands and their source. This file fetches
 * that list once, then sweeps the page for labels it recognises (ROCE, Debt /
 * Equity, P/E, Promoter holding, ...). Where it finds one with a number next to
 * it, it adds the ideal and a plain verdict - no per-panel wiring needed, so it
 * keeps working as panels change.
 *
 * Elements can also opt in explicitly:
 *   <span data-ideal="roce" data-actual="8.1">8.1%</span>
 */

(function () {
  "use strict";

  var BANDS = null;        /* key -> catalog entry */
  var RULES = null;        /* ordered label matchers */
  var LOADING = false;
  var DONE = new WeakSet();/* elements already enhanced */

  /* Label text -> ideal key. Order matters: longer/more specific first. */
  var MATCHERS = [
    [/\bdebt[\s\/-]*(to[\s\/-]*)?equity\b|\bd\/e\b/i, "debt_to_equity"],
    [/\breturn on capital\b|\broce\b/i, "roce"],
    [/\breturn on equity\b|\broe\b/i, "roe"],
    [/\boperating margin\b/i, "operating_margin"],
    [/\bnet (profit )?margin\b|\bnet margin\b/i, "net_profit_margin"],
    [/\binterest cover(age)?\b/i, "interest_coverage"],
    [/\bcash from (operations|ops)\b|\bcfo\b/i, "cfo_positive"],
    [/\bp[\s\/-]*e\b|\bprice[\s\/-]*(to[\s\/-]*)?earnings\b/i, "pe"],
    [/\bp[\s\/-]*b\b|\bprice[\s\/-]*(to[\s\/-]*)?book\b/i, "pb"],
    [/\bpeg\b/i, "peg"],
    [/\bdividend yield\b/i, "dividend_yield"],
    [/\bsales growth\b|\brevenue growth\b/i, "sales_growth_3y"],
    [/\bprofit growth\b|\bearnings growth\b/i, "profit_growth_3y"],
    [/\bpromoter( holding)?\b/i, "promoter_holding"],
    [/\bpledge(d)?\b/i, "pledge_pct"],
    [/\bfii( holding)?\b/i, "fii_holding"],
    [/\brisk\b.*%/i, "risk_pct"],
    [/\bshape score\b/i, "shape_score"],
    [/\b(chance of a good move|event score|p\(win\)|p_win)\b/i, "p_win"]
  ];

  function verdictClass(v) {
    if (v === "good") return "ideal-good";
    if (v === "ok") return "ideal-ok";
    if (v === "poor") return "ideal-poor";
    return "ideal-unknown";
  }

  /* Pull the first number out of a string like "8.1%" or "1,234.5 x". */
  function firstNumber(text) {
    if (!text) return null;
    var m = String(text).replace(/,/g, "").match(/-?\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }

  function keyForLabel(text) {
    if (!text) return null;
    for (var i = 0; i < MATCHERS.length; i++) {
      if (MATCHERS[i][0].test(text)) return MATCHERS[i][1];
    }
    return null;
  }

  function verdictFor(band, actual) {
    if (!band || actual === null || band.direction === undefined) return "unknown";
    var kind = band.direction || band.kind, good = band.good, ok = band.ok;
    if (kind === "higher") {
      if (good != null && actual >= good) return "good";
      if (ok != null && actual >= ok) return "ok";
      return "poor";
    }
    if (kind === "lower") {
      if (good != null && actual <= good) return "good";
      if (ok != null && actual <= ok) return "ok";
      return "poor";
    }
    return "unknown";
  }

  /* Decorate one label/value pair. */
  function enhance(labelEl, valueEl) {
    if (!labelEl || DONE.has(labelEl)) return;

    var key = labelEl.getAttribute("data-ideal") ||
      keyForLabel(labelEl.textContent);
    if (!key || !BANDS || !BANDS[key]) return;

    var band = BANDS[key];
    var actual = labelEl.hasAttribute("data-actual")
      ? parseFloat(labelEl.getAttribute("data-actual"))
      : firstNumber(valueEl ? valueEl.textContent : labelEl.textContent);
    if (actual === null || isNaN(actual)) return;

    var verdict = verdictFor(band, actual);
    DONE.add(labelEl);

    /* A small chip: "ideal 15% or more" plus a colour-coded dot. The colour is
       never the only signal - the words carry the meaning too. */
    var chip = document.createElement("span");
    chip.className = "ideal-chip " + verdictClass(verdict);
    chip.setAttribute("data-ideal-key", key);
    chip.setAttribute("title", band.ideal_text + " — " + band.source);
    chip.textContent = "ideal " + band.ideal_text;
    if (labelEl.parentNode) labelEl.parentNode.insertBefore(chip, labelEl.nextSibling);

    /* Make the whole row explainable in ordinary words. */
    if (!labelEl.hasAttribute("data-explain")) {
      labelEl.setAttribute("data-explain", key);
      labelEl.setAttribute("data-actual", String(actual));
      labelEl.style.cursor = "help";
    }
  }

  /* Sweep the page. Panels render asynchronously, so this repeats. */
  function sweep() {
    if (!BANDS) return;

    /* Common shapes: <div class="fx-row"><span>ROCE</span><strong>8.1%</strong>
       and <tr><td>ROCE</td><td>8.1</td></tr>. Handle both without touching
       panel code. */
    var rows = document.querySelectorAll(
      ".level, tr, .metric-card, .fund-row, .kpi, .stat, li");
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];

      var explicit = row.querySelector("[data-ideal][data-actual]");
      if (explicit) { enhance(explicit, null); continue; }

      var labelEl = row.querySelector("span, th, td:first-child, dt, label");
      if (!labelEl) continue;

      var valueEl = row.querySelector("strong, td:last-child, dd, .value, b");
      if (!valueEl || valueEl === labelEl) continue;

      enhance(labelEl, valueEl);
    }
  }

  function boot() {
    if (LOADING) return;
    LOADING = true;
    fetch("/api/ideals", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.ok) return;
        BANDS = {};
        (j.bands || []).forEach(function (b) { BANDS[b.key] = b; });
        sweep();
        /* Panels fill in over time; re-sweep cheaply. */
        var n = 0;
        var t = setInterval(function () {
          sweep();
          if (++n > 12) clearInterval(t);
        }, 1200);
      })
      .catch(function () { /* silent: the page must still work */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  /* Expose so a panel that renders later can force a sweep. */
  window.refreshIdeals = function () { sweep(); };
})();
