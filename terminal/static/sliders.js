/* sliders.js — the one slider the whole terminal reuses.
 *
 * WHY: the owner is not finance-literate and mostly works from a phone. Numbers
 * they can drag (money, risk, how far back to look) beat numbers they can only
 * read, because they can see the effect immediately. Every drag has to work
 * with one thumb and there is no build step, so this is a plain factory that
 * returns a real DOM element.
 *
 * USAGE
 *   var el = window.makeSlider({
 *     id: "whatifCapital",        // unique; also used for the label's `for`
 *     label: "Money you put in",  // plain words, no jargon
 *     min: 10000, max: 10000000, step: 5000, value: 500000,
 *     suffix: " rupees",          // optional, appended to the readout
 *     hint: "This is your whole pot, not just this one trade.",
 *     explainKey: "sizing",       // optional key from explain.py (GET /api/explain)
 *     format: function (v) {...}, // optional custom readout text
 *     onInput: function (v, el) {...}
 *   });
 *   someBox.appendChild(el);
 *
 * WHAT YOU GET
 *   a native <input type="range"> (so a phone drag works and the control is
 *   keyboard accessible out of the box), a live numeric readout, the low/high
 *   ends written underneath, and a "?" that opens the existing explanation
 *   dialog. The "?" carries data-explain and data-explain-stop, so explainer.js
 *   answers it and the label does NOT forward the tap to the slider.
 *
 * DELIBERATELY SMALL: no dependencies, no globals other than window.makeSlider,
 * and nothing here touches the network.
 */
(function () {
  "use strict";

  var SEQ = 0;

  function num(v, fallback) {
    var n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* Decimals are read off the step: step 5000 gives whole rupees, step 0.25
     gives two decimals. That is enough for every slider here and avoids a
     config flag nobody would remember to set. */
  function decimalsFor(step) {
    var s = String(step);
    var dot = s.indexOf(".");
    if (dot < 0) return 0;
    return Math.min(4, s.length - dot - 1);
  }

  /* 1234567 -> "12,34,567" (Indian grouping, the way the owner reads money). */
  function groupIndian(intText) {
    var s = String(intText);
    var neg = s.charAt(0) === "-";
    if (neg) s = s.slice(1);
    if (s.length <= 3) return (neg ? "-" : "") + s;
    var last3 = s.slice(-3);
    var rest = s.slice(0, -3);
    rest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    return (neg ? "-" : "") + rest + "," + last3;
  }

  function defaultFormat(v, step) {
    var dp = decimalsFor(step);
    var fixed = Number(v).toFixed(dp);
    var parts = fixed.split(".");
    return groupIndian(parts[0]) + (parts[1] ? "." + parts[1] : "");
  }

  function makeSlider(opts) {
    opts = opts || {};
    var id = String(opts.id || ("slider-" + (++SEQ)));
    var inputId = "sld-" + id.replace(/[^A-Za-z0-9_-]/g, "-");
    var min = num(opts.min, 0);
    var max = num(opts.max, 100);
    if (max <= min) max = min + 1;
    var step = num(opts.step, 1);
    if (step <= 0) step = 1;

    var fmt = typeof opts.format === "function"
      ? opts.format
      : function (v) { return defaultFormat(v, step); };
    var suffix = opts.suffix == null ? "" : String(opts.suffix);
    var onInput = typeof opts.onInput === "function" ? opts.onInput : null;

    var wrap = document.createElement("div");
    wrap.className = "slider-field";
    wrap.setAttribute("data-slider-id", id);

    var label = document.createElement("label");
    label.className = "slider-label";
    label.setAttribute("for", inputId);

    var text = document.createElement("span");
    text.className = "slider-label-text";
    text.textContent = opts.label == null ? "" : String(opts.label);
    label.appendChild(text);

    if (opts.explainKey) {
      var help = document.createElement("span");
      help.className = "ledger-sight slider-help";
      help.setAttribute("data-explain", String(opts.explainKey));
      /* Without the -stop flag the label would also move the slider when the
         "?" is tapped. */
      help.setAttribute("data-explain-stop", "1");
      help.setAttribute("role", "button");
      help.setAttribute("tabindex", "0");
      help.setAttribute("title", "Tap to learn what this means");
      help.setAttribute("aria-label",
        "What does " + String(opts.label || "this") + " mean?");
      help.textContent = "?";
      label.appendChild(help);
    }

    var readout = document.createElement("span");
    readout.className = "slider-readout";
    label.appendChild(readout);
    wrap.appendChild(label);

    var input = document.createElement("input");
    input.type = "range";
    input.className = "slider-range";
    input.id = inputId;
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    var start = num(opts.value, min);
    if (start < min) start = min;
    if (start > max) start = max;
    input.value = String(start);
    input.setAttribute("aria-label", String(opts.label || id));
    wrap.appendChild(input);

    if (opts.hint) {
      var hint = document.createElement("p");
      hint.className = "slider-hint";
      hint.textContent = String(opts.hint);
      wrap.appendChild(hint);
    }

    var ends = document.createElement("div");
    ends.className = "slider-ends";
    var lo = document.createElement("span");
    lo.textContent = fmt(min) + suffix;
    var hi = document.createElement("span");
    hi.textContent = fmt(max) + suffix;
    ends.appendChild(lo);
    ends.appendChild(hi);
    wrap.appendChild(ends);

    function paint(v) {
      var out;
      try { out = fmt(v); } catch (e) { out = String(v); }
      readout.textContent = out + suffix;
      input.setAttribute("aria-valuetext", out + suffix);
    }

    function current() { return num(input.value, start); }

    function emit() {
      var v = current();
      paint(v);
      if (onInput) onInput(v, wrap);
    }

    function setValue(v, silent) {
      var n = num(v, current());
      if (n < min) n = min;
      if (n > max) n = max;
      input.value = String(n);
      paint(n);
      if (!silent && onInput) onInput(n, wrap);
    }

    input.addEventListener("input", emit);
    /* A drag that ends exactly on the step already painted during `input`;
       this keeps a tap-to-jump honest without double-firing the callback. */
    input.addEventListener("change", function () { paint(current()); });

    paint(start);

    wrap.getValue = current;
    wrap.setValue = setValue;
    wrap.__range = input;
    return wrap;
  }

  window.makeSlider = makeSlider;
})();
