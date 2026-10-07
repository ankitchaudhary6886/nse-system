/* Keep the Model Event Score row inside the viewport long enough for a
   screenshot: re-assert the scroll on a timer while the async panels settle.
   Used with --post-expr-file (main world). */
(function () {
  var tries = 0;
  var last = "";
  function pin() {
    var row = document.querySelector("#setupSummary .fx-score-row");
    if (row) {
      var rect = row.getBoundingClientRect();
      if (rect.top < 70 || rect.bottom > window.innerHeight - 40) {
        window.scrollTo(0, Math.max(0, rect.top + window.scrollY - 110));
      }
      last = row.textContent.replace(/\s+/g, " ").trim();
    }
    if (tries++ < 40) setTimeout(pin, 150);
  }
  pin();
  return "pinning score row; text = " + (last || "(not rendered yet)");
})();
