/* Verify the real Model Event Score row as loadSymbol() rendered it. */
(function () {
  var row = document.querySelector("#setupSummary .fx-score-row");
  if (!row) {
    return JSON.stringify({
      rendered: false,
      setupSummaryHTML: (document.getElementById("setupSummary") || {}).innerHTML
        ? document.getElementById("setupSummary").innerHTML.slice(-400) : null,
    });
  }
  function lineCount(el) {
    var r = document.createRange();
    r.selectNodeContents(el);
    return r.getClientRects().length;
  }
  var label = row.querySelector(".fx-score-label");
  var labelText = label ? label.querySelector("span") : null;
  var val = row.querySelector(".fx-score-value");
  var chip = row.querySelector(".fx-score-target");
  var note = row.querySelector(".fx-score-note");
  var cs = getComputedStyle(val);
  return JSON.stringify({
    rendered: true,
    rowClass: row.className,
    rowHeight: Math.round(row.getBoundingClientRect().height),
    rowOverflows: row.scrollWidth > row.clientWidth + 1,
    labelLines: labelText ? lineCount(labelText) : null,
    labelText: labelText ? labelText.textContent.trim() : null,
    labelClipped: label ? label.scrollWidth > label.clientWidth + 1 : null,
    valueText: val.textContent,
    valueLines: lineCount(val),
    valueFont: cs.fontFamily.split(",")[0],
    valueTabular: cs.fontVariantNumeric,
    valueWhiteSpace: cs.whiteSpace,
    chipText: chip ? chip.textContent : null,
    chipVisible: chip ? getComputedStyle(chip).display !== "none" : null,
    noteText: note ? note.textContent.trim() : null,
    helpButton: !!row.querySelector(".fx-help"),
  });
})();
