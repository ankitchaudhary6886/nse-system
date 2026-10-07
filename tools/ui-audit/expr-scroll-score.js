/* Scroll the window so the Model Event Score row sits near the top of the
   viewport, for a readable screenshot. Used with --expr-file (main world). */
(function () {
  var row = document.querySelector("#setupSummary .fx-score-row");
  if (!row) return "no score row";
  var y = row.getBoundingClientRect().top + window.scrollY - 90;
  window.scrollTo(0, Math.max(0, y));
  return "scrolled to " + Math.round(y) + " (row text: " + row.textContent.replace(/\s+/g, " ").trim() + ")";
})();
