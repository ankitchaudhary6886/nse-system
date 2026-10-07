/* Verify the refactored knowledge popup in the real browser, across all tiers.
   Returns a promise so eval.mjs (awaitPromise:true) waits for the real result.
   Clicks a throwaway [data-explain] element so the delegated listener runs
   exactly as it does for a real user target. */
(async function () {
  var dialog = document.getElementById("dataDetailDialog");
  var body = document.getElementById("dataDetailBody");
  var title = document.getElementById("dataDetailTitle");
  var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var out = {};

  function snapshot() {
    var text = (body ? body.textContent : "") || "";
    return {
      open: dialog.open === true || getComputedStyle(dialog).display !== "none",
      title: title ? title.textContent.trim() : null,
      headline: (body && body.querySelector(".ex-headline")) ? body.querySelector(".ex-headline").textContent.trim() : null,
      rows: body ? body.querySelectorAll(".ex-row").length : 0,
      rowLabels: body ? Array.prototype.map.call(body.querySelectorAll(".ex-label"), function (e) { return e.textContent.trim(); }) : [],
      caution: (body && body.querySelector(".ex-caution")) ? body.querySelector(".ex-caution").textContent.trim() : null,
      hasFoot: !!(body && body.querySelector(".ex-foot")),
      legacyTier: dialog.getAttribute("data-explain-legacy"),
      openKey: dialog.getAttribute("data-explain-open"),
      bodyChars: text.length,
      bodyText: text.replace(/\s+/g, " ").trim().slice(0, 300),
    };
  }

  async function probeKey(key, label) {
    var probe = document.createElement("span");
    probe.setAttribute("data-explain", key);
    probe.setAttribute("data-explain-stop", "");
    probe.textContent = label || key;
    probe.style.cssText = "position:fixed;left:-9999px;top:0";
    document.body.appendChild(probe);
    probe.click();
    await wait(1100);
    var s = snapshot();
    s.leaksKeyInTitle = key ? (String(s.title) + " " + String(s.headline)).indexOf(key) >= 0 : null;
    out[key] = s;
    if (probe.parentNode) probe.parentNode.removeChild(probe);
    if (dialog.open) dialog.close();
    await wait(200);
  }

  /* Tier 1: fully migrated key. */
  await probeKey("p_win");
  /* Tier 1 again, different key, to prove the shape does not vary. */
  await probeKey("setup");
  /* Tier 3: a key with no explain entry but a sibling .ideal-chip in the DOM. */
  await probeKey("roce", "ROCE");
  /* Tier 4: unknown key, no chip anywhere. */
  await probeKey("zzz-totally-unknown-key", "Mystery Figure");

  /* Shape comparison across two fully migrated keys. */
  out._shapeConsistent = out.p_win && out.setup
    ? (out.p_win.rows === out.setup.rows && !!out.p_win.headline && !!out.setup.headline)
    : null;
  return JSON.stringify(out, null, 1);
})();
