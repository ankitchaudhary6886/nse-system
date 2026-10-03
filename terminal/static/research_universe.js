// Research Universe — every setup today, with cached historical stats.
// Sortable columns. Colour-coded n reliability.

// Module-level state
let _universeRows = [];
let _sortKey = "n_setups";
let _sortDir = -1;   // -1 = desc, 1 = asc

const _COLUMNS = [
  { key: "symbol",         label: "Symbol",   align: "left" },
  { key: "source",         label: "Src",      align: "left" },
  { key: "sector",         label: "Sector",   align: "left" },
  { key: "pct_from_52w_high", label: "52wHi%", align: "right" },
  { key: "n_setups",       label: "n",        align: "right" },
  { key: "n_triggered",    label: "trig",     align: "right" },
  { key: "p_trigger",      label: "P(trig)",  align: "right" },
  { key: "p_1r",           label: "P+1R",     align: "right" },
  { key: "p_2r",           label: "P+2R",     align: "right" },
  { key: "p_3r",           label: "P+3R",     align: "right" },
  { key: "median_mfe_r",   label: "MFE",      align: "right" },
  { key: "median_mae_r",   label: "MAE",      align: "right" },
];


function _nReliabilityClass(n) {
  if (n == null) return "rel-none";
  if (n >= 10) return "rel-strong";
  if (n >= 5) return "rel-mod";
  if (n >= 1) return "rel-thin";
  return "rel-none";
}

function _pct(v) {
  if (v == null) return "—";
  return (v * 100).toFixed(0) + "%";
}
function _num(v, dp) {
  if (v == null) return "—";
  return Number(v).toFixed(dp == null ? 2 : dp);
}

function _sortValue(row, key) {
  const v = row[key];
  if (v == null || v === "") return null;
  if (typeof v === "number") return v;
  if (typeof v === "string") return v.toLowerCase();
  return v;
}

function _sortedRows() {
  const rows = _universeRows.slice();
  rows.sort((a, b) => {
    const av = _sortValue(a, _sortKey);
    const bv = _sortValue(b, _sortKey);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;               // nulls last
    if (bv == null) return -1;
    if (av < bv) return -1 * _sortDir;
    if (av > bv) return 1 * _sortDir;
    return 0;
  });
  return rows;
}

function _headerCell(col) {
  const active = _sortKey === col.key;
  const arrow = active ? (_sortDir === -1 ? " ▼" : " ▲") : "";
  const color = active ? "#60a5fa" : "#9fb0cc";
  const sort = active ? (_sortDir === -1 ? "descending" : "ascending") : "none";
  return `<th data-sort="${col.key}" tabindex="0"
    aria-label="${col.label}; press Enter to sort" aria-sort="${sort}"
    style="text-align:${col.align}; color:${color};
    cursor:pointer; padding:6px 4px; user-select:none;">${col.label}${arrow}</th>`;
}

function _renderUniverseTable() {
  const rows = _sortedRows();
  let html = `<table style="width:100%; border-collapse:collapse; font-size:12px;">
    <thead>
      <tr style="border-bottom:1px solid rgba(255,255,255,.1);">
        ${_COLUMNS.map(_headerCell).join("")}
      </tr>
    </thead><tbody>`;
  rows.forEach(r => {
    const rel = _nReliabilityClass(r.n_setups);
    const cacheStr = r.n_setups == null
      ? `<span style="color:#fbbf24;">${r.analysis_error ? "unavailable" : "—"}</span>`
      : `<span class="rel-pill ${rel}">${r.n_setups}</span>`;
    const hi = r.pct_from_52w_high;
    const hiStr = hi == null ? "—" : hi.toFixed(1);
    html += `<tr class="click-row" tabindex="0" role="button"
      aria-label="Open research for ${r.symbol}"
      style="border-bottom:1px solid rgba(255,255,255,.05);" data-sym="${r.symbol}">
      <td style="padding:6px 4px;"><b>${r.symbol}</b></td>
      <td style="padding:6px 4px; color:#7f8da9;">${r.source || ""}</td>
      <td style="padding:6px 4px; color:#7f8da9;">${r.sector || "—"}</td>
      <td style="padding:6px 4px; text-align:right;">${hiStr}</td>
      <td style="padding:6px 4px; text-align:right;">${cacheStr}</td>
      <td style="padding:6px 4px; text-align:right;">${r.n_triggered ?? "—"}</td>
      <td style="padding:6px 4px; text-align:right;">${_pct(r.p_trigger)}</td>
      <td style="padding:6px 4px; text-align:right;">${_pct(r.p_1r)}</td>
      <td style="padding:6px 4px; text-align:right;">${_pct(r.p_2r)}</td>
      <td style="padding:6px 4px; text-align:right;">${_pct(r.p_3r)}</td>
      <td style="padding:6px 4px; text-align:right;">${_num(r.median_mfe_r)}</td>
      <td style="padding:6px 4px; text-align:right;">${_num(r.median_mae_r)}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  html += `<p style="color:#7f8da9; font-size:11px; margin-top:10px;">
    Reliability: <span class="rel-pill rel-strong">≥10</span> robust ·
    <span class="rel-pill rel-mod">5-9</span> moderate ·
    <span class="rel-pill rel-thin">1-4</span> anecdotal ·
    <span class="rel-pill rel-none">0</span> none.
    Click any header to sort.
  </p>`;
  return html;
}

async function loadResearchUniverse(computeMissing) {
  const box = document.getElementById("researchUniverseBox");
  const badge = document.getElementById("researchUniverseBadge");
  const refresh = document.getElementById("refreshResearchUniverse");
  const compute = document.getElementById("computeMissingBtn");
  if (!box) return;
  const button = computeMissing ? compute : refresh;
  if (button) {
    button.disabled = true;
    button.dataset.previousText = button.textContent;
    button.textContent = computeMissing ? "Computing…" : "Refreshing…";
  }
  box.innerHTML = "<p>Loading...</p>";
  try {
    const url = "/api/research-universe" +
      (computeMissing ? "?compute_missing=true" : "");
    const data = await api(url);
    if (data.error) throw new Error(data.error);
    _universeRows = data.rows || [];
    if (!_universeRows.length) {
      box.innerHTML = data.date
        ? `<p>No setups were stored for the latest scan date (${data.date}). Price data: ${data.source_dates?.prices || "unavailable"}.</p>`
        : "<p>No trader scans are stored yet. Run the swing or trend scan, then refresh this view.</p>";
      if (badge) badge.textContent = data.date ? `0 setups · ${data.date}` : "no scan data";
      return;
    }
    const stale = data.stale ? " · scan older than stored prices" : "";
    const missing = data.n_errors ? ` · ${data.n_errors} history unavailable` : "";
    if (badge) badge.textContent =
      `${_universeRows.length} symbols · ${data.date || "date unavailable"}${stale}${missing}`;
    box.innerHTML = (data.stale
      ? `<p class="method-warning">The latest scan is older than the newest stored price bar (${data.source_dates?.prices || "unknown"}). Refresh price data and rerun the scan before relying on this result.</p>`
      : "") + _renderUniverseTable();
    _bindUniverseEvents(box);
  } catch (e) {
    box.textContent = `Research universe error: ${e.message}`;
    if (badge) badge.textContent = "unavailable";
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = button.dataset.previousText ||
        (computeMissing ? "Compute Missing" : "Refresh");
      delete button.dataset.previousText;
    }
  }
}
window.loadResearchUniverse = loadResearchUniverse;

function _bindUniverseEvents(box) {
  // header clicks → sort
  box.querySelectorAll("th[data-sort]").forEach(th => {
    const sort = () => {
      const key = th.dataset.sort;
      if (_sortKey === key) {
        _sortDir = -_sortDir;
      } else {
        _sortKey = key;
        _sortDir = -1;   // default: descending on new column
      }
      box.innerHTML = _renderUniverseTable();
      _bindUniverseEvents(box);
    };
    th.addEventListener("click", sort);
    th.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        sort();
      }
    });
  });
  // row clicks → jump
  box.querySelectorAll("tr[data-sym]").forEach(tr => {
    const open = () => window.jumpResearch(tr.dataset.sym);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

async function computeMissing() {
  await loadResearchUniverse(true);
}

window.jumpResearch = function(sym) {
  setView("overview");
  loadSymbol(sym);
};

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshResearchUniverse");
  if (btn) btn.addEventListener("click", () => loadResearchUniverse(false));
  const cb = document.getElementById("computeMissingBtn");
  if (cb) cb.addEventListener("click", computeMissing);
});