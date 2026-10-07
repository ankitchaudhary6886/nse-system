/* Verify the "Model Event Score" card holds its single line at phone width.
   The card only renders when the model metadata exists, and this environment has
   no stored p_win, so we inject the exact markup loadSymbol() emits and measure it. */
(function () {
  var host = document.getElementById("setupSummary");
  if (!host) return JSON.stringify({ error: "no #setupSummary" });
  host.innerHTML =
    '<div class="model-explainer">' +
    '<div class="fx-score-row is-neut">' +
    '<span class="fx-score-label"><span>Model Event Score</span>' +
    '<button type="button" class="fx-help">?</button></span>' +
    '<span class="fx-score-target">Target &gt;50%</span>' +
    '<span class="fx-score-value">43%</span>' +
    "</div></div>";

  var row = host.querySelector(".fx-score-row");
  var label = row.querySelector(".fx-score-label");
  var val = row.querySelector(".fx-score-value");
  var chip = row.querySelector(".fx-score-target");
  var labelSpan = label.querySelector("span");

  function lineCount(el) {
    var r = document.createRange();
    r.selectNodeContents(el);
    return r.getClientRects().length;
  }

  return JSON.stringify({
    hostWidth: Math.round(host.getBoundingClientRect().width),
    rowHeight: Math.round(row.getBoundingClientRect().height),
    rowOverflows: row.scrollWidth > row.clientWidth + 1,
    labelLines: lineCount(labelSpan),
    labelText: labelSpan.textContent,
    labelWidth: Math.round(label.getBoundingClientRect().width),
    labelClipped: label.scrollWidth > label.clientWidth + 1,
    labelWhiteSpace: getComputedStyle(label).whiteSpace,
    labelWordBreak: getComputedStyle(label).wordBreak,
    labelOverflowWrap: getComputedStyle(label).overflowWrap,
    valueLines: lineCount(val),
    valueText: val.textContent,
    valueFont: getComputedStyle(val).fontFamily.split(",")[0],
    valueTabular: getComputedStyle(val).fontVariantNumeric,
    valueWidth: Math.round(val.getBoundingClientRect().width),
    chipText: chip.textContent,
    chipVisible: getComputedStyle(chip).display !== "none",
  });
})();
