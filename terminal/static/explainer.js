/* explainer.js - "click anything, understand it" layer.
 *
 * WHY: the owner is not a finance person. Every number and label on screen must
 * be answerable in ordinary words, on demand, without jargon.
 *
 * WHAT THE CLICK SHOWS NOW (the decision-first card):
 *   one headline  - the single most important thing about this item
 *   + up to 4 rows - what it is / how to use it / how to spot it / do this next
 *   + an optional "Careful" line for a real trap
 *   and never a developer footer, never a wall of seven equal paragraphs.
 *
 * HOW TO USE: put `data-explain="regime"` on anything clickable. Keys come from
 * explain.py (GET /api/explain lists them), or from ideal.py when the key is an
 * "actual vs ideal" measure such as ROCE. Nothing else is needed - this file
 * attaches one delegated listener, so elements added later are covered too.
 *
 * NEVER AN EMPTY SHELL: five tiers, resolved in order (spec section D).
 *   1. the entry has a headline            -> render the card
 *   2. legacy entry, no headline yet       -> derive one from `what` (bridge)
 *   3. unknown key with an ideal band      -> card built from the on-screen chip
 *   4. truly unknown key                   -> "no note stored yet" card
 *   5. request failed and nothing cached   -> "could not load" card
 * The raw key is never printed: it only appears in `data-explain-open`.
 *
 * The text lives in explain.py, not here, so the terminal, the API and the
 * alerts can never disagree about what a word means.
 */
(function () {
  "use strict";

  var CACHE = {};        /* key -> last successful /api/explain payload */
  var IDEALS = null;     /* key -> ideal band, loaded once, lazily */
  var MAX_HEADLINE = 70;

  /* The render contract (spec A.3). Labels are fixed here as well as in
   * explain.POPUP_SECTIONS, because tiers 2-5 render with no entry at all. */
  var POPUP_ORDER = [
    ["what", "What it is"],
    ["use", "How to use it"],
    ["spot", "How to spot it"],
    ["action", "Do this next"]
  ];
  var LABELS = {};
  POPUP_ORDER.forEach(function (p) { LABELS[p[0]] = p[1]; });

  var CAUTION_LABEL = "Careful";
  var HEADLINE_EMPTY = "No plain-language note is stored for this yet";
  var HEADLINE_FAILED = "Could not load the note right now";
  var TIER4_NOTE = "Notes live in one file, so every screen says the same thing.";
  var TIER3_WHAT = "Compare the figure beside it with that level. A figure below " +
    "it is a weak spot, not a verdict on the company.";
  var TIER3_SPOT = "The label you just tapped, with the ideal chip beside it.";
  var TIER3_ACTION = "Read the number against the level before using it in a " +
    "decision.";

  function dialog() {
    return document.getElementById("dataDetailDialog");
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tidy(s) {
    return String(s == null ? "" : s).replace(/\s+/g, " ").trim();
  }

  /* A headline is one line: no trailing full stop, and cut on a word boundary
   * rather than mid-word (spec D, tier 2). No ellipsis - it is a headline, not
   * a quote. */
  function asHeadline(text, limit) {
    var t = tidy(text).replace(/[.!?,;:]+$/, "");
    if (t.length <= limit) return t;
    var cut = t.slice(0, limit + 1);
    var sp = cut.lastIndexOf(" ");
    if (sp > 0) cut = cut.slice(0, sp);
    return cut.replace(/[\s,;:.\-]+$/, "");
  }

  function firstSentence(text) {
    var t = tidy(text);
    var m = t.match(/^.*?[.!?](?=\s|$)/);
    return m ? m[0] : t;
  }

  function labelFor(el) {
    if (!el) return "";
    var t = "";
    if (el.getAttribute) t = tidy(el.getAttribute("aria-label"));
    if (!t) t = tidy(el.textContent);
    return t;
  }

  function panelHeading(el) {
    var host = el && el.closest ? el.closest("section, .panel, .card, dialog") : null;
    if (!host || !host.querySelector) return "";
    var h = host.querySelector("h1, h2, h3");
    return h ? tidy(h.textContent) : "";
  }

  function fallbackLabel(el) {
    return asHeadline(labelFor(el) || panelHeading(el), MAX_HEADLINE) || "This item";
  }

  /* ------------------------------------------------------------- tier 1 -- */
  /* The authored card. Empty-string fields are skipped, never rendered blank. */
  function tier1Card(entry) {
    var head = tidy(entry.headline);
    if (!head) return null;
    var rows = [];
    POPUP_ORDER.forEach(function (pair) {
      var text = tidy(entry[pair[0]]);
      if (text) rows.push({ key: pair[0], label: pair[1], text: text });
    });
    if (!rows.length) return null;   /* invariant 4: never a titled blank box */
    return {
      tier: 1,
      title: tidy(entry.title) || "This item",
      headline: asHeadline(head, MAX_HEADLINE),
      rows: rows,
      caution: tidy(entry.caution),
      note: ""
    };
  }

  /* ------------------------------------------------------------- tier 2 -- */
  /* The migration bridge: a legacy entry that has no headline yet still opens a
   * real card, derived from the fields that do exist. */
  function tier2Card(entry) {
    var what = tidy(entry.what);
    var head = asHeadline(firstSentence(what), MAX_HEADLINE);
    if (!head) return null;
    var rows = [];
    var sources = [
      ["what", what],
      ["use", tidy(entry.look)],
      ["spot", tidy(entry.sight) || tidy(entry.where)],
      ["action", tidy(entry.when)]
    ];
    sources.forEach(function (pair) {
      if (pair[1]) rows.push({ key: pair[0], label: LABELS[pair[0]], text: pair[1] });
    });
    if (!rows.length) return null;
    return {
      tier: 2,
      title: tidy(entry.title) || "This item",
      headline: head,
      rows: rows,
      caution: tidy(entry.caution),
      note: ""
    };
  }

  /* ------------------------------------------------------------- tier 3 -- */
  /* An unknown key that still has an ideal band on screen (ROCE, P/E, pledge,
   * the growth and margin measures...). ideals.js already put a `.ideal-chip`
   * next to the label, so the card writes itself from data the page shows. */
  function isChip(node, key) {
    if (!node || !node.classList || !node.classList.contains("ideal-chip")) return false;
    var own = node.getAttribute("data-ideal-key");
    /* ideals.js always stamps the key; a hand-written chip without one is still
     * accepted when it sits right beside the label. */
    return !own || !key || own === key;
  }

  function chipBand(el, key) {
    if (!el) return null;
    var node = isChip(el.nextElementSibling, key) ? el.nextElementSibling : null;
    if (!node && isChip(el.previousElementSibling, key)) node = el.previousElementSibling;
    if (!node && el.parentNode && el.parentNode.querySelectorAll) {
      var chips = el.parentNode.querySelectorAll(".ideal-chip");
      for (var i = 0; i < chips.length && !node; i++) {
        if (isChip(chips[i], key)) node = chips[i];
      }
    }
    if (!node) return null;
    var text = tidy(node.textContent).replace(/^ideal\s+/i, "");
    if (!text) return null;
    return {
      key: node.getAttribute("data-ideal-key") || key,
      ideal_text: text,
      title: tidy(node.getAttribute("title")),
      label: labelFor(el)
    };
  }

  function loadIdeals() {
    if (IDEALS) return Promise.resolve(IDEALS);
    return fetch("/api/ideals", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.ok) return null;
        var map = {};
        (j.bands || []).forEach(function (b) { map[b.key] = b; });
        IDEALS = map;
        return map;
      })
      .catch(function () { return null; });
  }

  function bandFor(key, el) {
    var onScreen = chipBand(el, key);
    if (onScreen) return Promise.resolve(onScreen);
    return loadIdeals().then(function (map) {
      var b = map && map[key];
      if (!b) return null;
      return {
        key: key,
        ideal_text: tidy(b.ideal_text),
        title: tidy(b.ideal_text) + " \u2014 " + tidy(b.source),
        label: tidy(b.label)
      };
    });
  }

  /* The band text can carry a caveat after a separator ("under 1.0x - growth
   * costs less than it is worth"). The headline keeps the level; the `what` row
   * keeps the whole definition. */
  function bandPhrase(ideal) {
    return tidy(ideal).split(/\s*[;(]\s*|\s+-\s+/)[0];
  }

  function tier3Card(key, band) {
    var label = asHeadline(band.label || band.key || key, MAX_HEADLINE) || "This item";
    var ideal = tidy(band.ideal_text);
    var definition = tidy(band.title);
    var cut = definition.indexOf(" \u2014 ");
    if (cut > 0) definition = definition.slice(0, cut);
    if (!definition) definition = ideal;
    var head = asHeadline("The level we look for here is " + (bandPhrase(ideal) || ideal),
      MAX_HEADLINE);
    var rows = [];
    if (definition) {
      rows.push({ key: "what", label: LABELS.what, text: label + " - " + definition });
    }
    rows.push({ key: "use", label: LABELS.use, text: TIER3_WHAT });
    rows.push({ key: "spot", label: LABELS.spot, text: TIER3_SPOT });
    rows.push({ key: "action", label: LABELS.action, text: TIER3_ACTION });
    return {
      tier: 3,
      title: label,
      headline: head,
      rows: rows,
      caution: "",
      note: ""
    };
  }

  /* --------------------------------------------------------- tiers 4, 5 -- */
  function bareCard(el, failed) {
    var label = fallbackLabel(el);
    return {
      tier: failed ? 5 : 4,
      title: label,
      headline: failed ? HEADLINE_FAILED : HEADLINE_EMPTY,
      rows: [
        { key: "what", label: LABELS.what,
          text: "You tapped " + label + ". It is a value the terminal is showing " +
                "you, and its meaning has not been written down yet." },
        { key: "spot", label: LABELS.spot,
          text: "It is the " + label + " you just tapped." }
      ],
      caution: "",
      note: failed ? "" : TIER4_NOTE
    };
  }

  /* ------------------------------------------------------------ resolve -- */
  function resolve(key, el, payload) {
    if (payload && payload.ok && payload.entry) {
      var one = tier1Card(payload.entry);
      if (one) return Promise.resolve(one);
      var two = tier2Card(payload.entry);
      if (two) return Promise.resolve(two);
    }
    return bandFor(key, el).then(function (band) {
      if (band) return tier3Card(key, band);
      /* A response that says "no explanation stored" - or an entry with nothing
       * usable in it - is tier 4. No usable body at all (network error, bad
       * JSON, non-200) is tier 5. */
      return bareCard(el, !payload);
    });
  }

  function cardHtml(card) {
    var html = '<p class="ex-headline">' + esc(card.headline) + "</p>";
    card.rows.forEach(function (r) {
      var cls = "ex-row";
      if (r.key === "spot") cls += " ex-spot";
      if (r.key === "action") cls += " ex-action";
      html += '<div class="' + cls + '">' +
        '<span class="ex-label">' + esc(r.label || LABELS[r.key] || r.key) + "</span>" +
        " " +
        '<span class="ex-text">' + esc(r.text) + "</span></div>";
    });
    if (card.caution) {
      html += '<p class="ex-caution">' +
        '<span class="ex-label">' + esc(CAUTION_LABEL) + "</span>" +
        " " +
        '<span class="ex-text">' + esc(card.caution) + "</span></p>";
    }
    if (card.note) html += '<p class="ex-note">' + esc(card.note) + "</p>";
    return html;
  }

  function draw(key, card) {
    var d = dialog();
    if (!d) return card;
    var titleEl = document.getElementById("dataDetailTitle");
    var body = document.getElementById("dataDetailBody");
    if (!titleEl || !body) return card;

    titleEl.textContent = card.title;
    body.innerHTML = cardHtml(card);
    /* The key is allowed here and nowhere else in visible text. */
    d.setAttribute("data-explain-open", String(key));
    d.setAttribute("data-explain-tier", String(card.tier));
    if (card.tier === 2) d.setAttribute("data-explain-legacy", "1");
    else d.removeAttribute("data-explain-legacy");
    if (d.showModal && !d.open) { try { d.showModal(); } catch (e) {} }
    return card;
  }

  function render(key, payload, el) {
    return resolve(key, el, payload).then(function (card) {
      draw(key, card);
      return card;
    });
  }

  function open(key, el) {
    key = tidy(key);
    if (!key) return Promise.resolve(null);
    if (CACHE[key]) return render(key, CACHE[key], el);
    return fetch("/api/explain/" + encodeURIComponent(key), {
      credentials: "same-origin"
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && j.ok) CACHE[key] = j;
        return render(key, j, el);
      })
      .catch(function () { return render(key, null, el); });
  }

  /* One delegated listener covers every present and future element.
   *
   * Two behaviours, chosen per element:
   *   data-explain            -> show the explanation AND let the element do its
   *                              own job (nav buttons still navigate, metric
   *                              cards still switch view).
   *   data-explain-stop       -> show the explanation INSTEAD of the surrounding
   *                              action. Used for figures inside a row that would
   *                              otherwise navigate away on click.
   *
   * Capture phase, so this decides before the row's own handler runs.
   */
  document.addEventListener("click", function (ev) {
    var el = ev.target.closest ? ev.target.closest("[data-explain]") : null;
    if (!el) return;
    if (el.hasAttribute("data-explain-stop")) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    open(el.getAttribute("data-explain"), el);
  }, true);

  /* Keyboard: Enter/Space on anything marked as an explain target. */
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    var el = ev.target.closest ? ev.target.closest("[data-explain]") : null;
    if (!el) return;
    if (el.tagName === "BUTTON" || el.tagName === "A") return; /* native */
    ev.preventDefault();
    open(el.getAttribute("data-explain"), el);
  });

  window.openExplain = open;
})();
