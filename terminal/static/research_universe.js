// Research Universe — every setup today, with cached historical stats.
// Owner scans and picks. No recommendations.

async function loadResearchUniverse(computeMissing) {
  const box = document.getElementById("researchUniverseBox");
  const badge = document.getElementById("researchUniverseBadge");
  if (!box) return;
  box.innerHTML = "<p>Loading...</p>";
  try {
    const url = "/api/research-universe" +
      (computeMissing ? "?compute_missing=true" : "");
    const data = await api(url);
    const rows = data.rows || [];
    if (!rows.length) {
      box.innerHTML = "<p>No setups today.</p>";
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${rows.length} setups · ${data.date}`;

    let html = `<table style="width:100%; border-collapse:collapse; font-size:12px;">
      <thead>
        <tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
          <th style="padding:6px 4px;">Symbol</th>
          <th style="padding:6px 4px;">Src</th>
          <th style="padding:6px 4px;">Sector</th>
          <th style="padding:6px 4px;">52wHi%</th>
          <th style="padding:6px 4px;">n</th>
          <th style="padding:6px 4px;">trig</th>
          <th style="padding:6px 4px;">P+1R</th>
          <th style="padding:6px 4px;">P+2R</th>
          <th style="padding:6px 4px;">P+3R</th>
          <th style="padding:6px 4px;">MFE</th>
          <th style="padding:6px 4px;">MAE</th>
          <th style="padding:6px 4px;">Cache</th>
        </tr>
      </thead>
      <tbody>`;
    rows.forEach(r => {
      const p = (v) => v == null ? "—" : (v * 100).toFixed(0) + "%";
      const n = (v) => v == null ? "—" : Number(v).toFixed(2);
      const cacheStr = (r.n_setups == null)
        ? `<span style="color:#fbbf24;">miss</span>`
        : "ok";
      const hi = r.pct_from_52w_high;
      const hiStr = hi == null ? "—" : hi.toFixed(1) + "%";
      html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05); cursor:pointer;"
        onclick="jumpResearch('${r.symbol}')">
        <td style="padding:6px 4px;"><b>${r.symbol}</b></td>
        <td style="padding:6px 4px; color:#7f8da9;">${r.source}</td>
        <td style="padding:6px 4px; color:#7f8da9;">${r.sector || "—"}</td>
        <td style="padding:6px 4px;">${hiStr}</td>
        <td style="padding:6px 4px;">${r.n_setups ?? "—"}</td>
        <td style="padding:6px 4px;">${r.n_triggered ?? "—"}</td>
        <td style="padding:6px 4px;">${p(r.p_1r)}</td>
        <td style="padding:6px 4px;">${p(r.p_2r)}</td>
        <td style="padding:6px 4px;">${p(r.p_3r)}</td>
        <td style="padding:6px 4px;">${n(r.median_mfe_r)}R</td>
        <td style="padding:6px 4px;">${n(r.median_mae_r)}R</td>
        <td style="padding:6px 4px;">${cacheStr}</td>
      </tr>`;
    });
    html += `</tbody></table>`;
    html += `<p style="color:#7f8da9; font-size:11px; margin-top:10px;">
      "miss" = not cached yet. Press <b>Compute Missing</b> to fill
      (slow — 5-15s per symbol). Otherwise press Compute in the Overview tab for individual symbols.
    </p>`;
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<p>Research universe error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

async function computeMissing() {
  const btn = document.getElementById("computeMissingBtn");
  if (btn) btn.textContent = "Computing (slow)...";
  await loadResearchUniverse(true);
  if (btn) btn.textContent = "Compute Missing";
}

window.jumpResearch = function(sym) {
  setView("overview");
  loadSymbol(sym);
  if (window.loadResearch) setTimeout(() => window.loadResearch(sym), 500);
};

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshResearchUniverse");
  if (btn) btn.addEventListener("click", () => loadResearchUniverse(false));
  const cb = document.getElementById("computeMissingBtn");
  if (cb) cb.addEventListener("click", computeMissing);
});