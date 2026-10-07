/* Render the REAL Model Event Score row through loadSymbol(), with a stubbed
   /api/meta response so the p_win-present branch is exercised.
   Injected via Page.addScriptToEvaluateOnNewDocument, so it patches fetch before
   any app script runs and mutates nothing in the repo.
   Reports through window.name (the one string property that crosses worlds). */
(function () {
  var realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf("/api/meta/") >= 0) {
      return Promise.resolve(new Response(JSON.stringify({
        symbol: "KEI",
        p_win: 0.43,
        target_pct: 0.5,
        why: [
          { feature: "slope200", impact: 0.31 },
          { feature: "vcr", impact: 0.22 },
          { feature: "mom3", impact: -0.14 },
          { feature: "above200", impact: 0.09 },
        ],
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    return realFetch(input, init);
  };

  function measure() {
    var row = document.querySelector("#setupSummary .fx-score-row");
    var detail = document.querySelector("#setupSummary details.fx-method");
    if (!row) { window.name = JSON.stringify({ rendered: false }); return; }
    function lineCount(el) {
      if (!el) return null;
      var r = document.createRange();
      r.selectNodeContents(el);
      return r.getClientRects().length;
    }
    var labelWrap = row.querySelector(".fx-score-label");
    var label = labelWrap.querySelector("span");
    var val = row.querySelector(".fx-score-value");
    var chip = row.querySelector(".fx-score-target");
    window.name = JSON.stringify({
      rendered: true,
      rowClass: row.className,
      labelText: label.textContent.trim(),
      labelLines: lineCount(label),
      labelClipped: labelWrap.scrollWidth > labelWrap.clientWidth + 1,
      valueText: val.textContent,
      valueLines: lineCount(val),
      valueFont: getComputedStyle(val).fontFamily.split(",")[0],
      valueTabular: getComputedStyle(val).fontVariantNumeric,
      valueColor: getComputedStyle(val).color,
      chipText: chip.textContent,
      chipVisible: getComputedStyle(chip).display !== "none",
      rowHeight: Math.round(row.getBoundingClientRect().height),
      rowOverflows: row.scrollWidth > row.clientWidth + 1,
      shapDetailsRendered: !!detail,
      shapRows: detail ? detail.querySelectorAll(".fx-row").length : 0,
    });
  }

  if (document.readyState === "complete") setTimeout(measure, 6000);
  else window.addEventListener("load", function () { setTimeout(measure, 6000); });
})();
