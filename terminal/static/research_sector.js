// Research Sectors — pooled setups by sector. Real aggregation, not
// average-of-averages: pulls raw setups from every cached symbol
// in the sector and recomputes.

let _sectorRows = [];
let _sectorSortKey = "n_setups";
let _sectorSortDir = -1;

const _SECTOR_COLUMNS = [
  { key: "sector",     label: "Sector" },
  { key: "n_symbols",  label: "syms" },
  { key: "n_setups",   label: "n" },
  { key: "n_triggered", label: "trig" },
  { key: "p_trigger",  label: "P(trig)" },
  { key: "p_1r_given_trigger", label: "P+1R" },
  { key: "p_2r_given_trigger", label: "P+2R" },
  { key: "p_3r_given_trigger", label: "P+3R" },
  { key: "median_mfe_r", label: "MFE" },
  { key: "median_mae_r", label: "MAE" },
];

function _secPct(v) {
  if (v == null) return "—";
  return (v * 100).toFixed(0) + "%";
}
function _secNum(v, dp) {
  if (v == null) return "—";
  return Number(v).toFixed(dp == null ? 2 : dp);
}
function _sectorRowReliability(n) {
  if (n == null) return "rel-none";
  if (n >= 30) return "rel-strong";
  if (n >= 15) return "rel-mod";
  if (n >= 1) return "rel-thin";
  return "rel-none";
}

function _sectorSorted() {
  const rows = _sectorRows.slice();
  rows.sort((a, b) => {
    const av = a[_sectorSortKey];
    const bv = b[_sectorSortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "string") {
      return av.localeCompare(bv) * _sectorSortDir;
    }
    if (av < bv) return -1 * _sectorSortDir;
    if (av > bv) return 1 * _sectorSortDir;
    return 0;
  });
  return rows;
}

function _secHeaderCell(col) {
  const active = _sectorSortKey === col.key;
  const arrow = active ? (_sectorSortDir === -1 ? " ▼" : " ▲") : "";
  const color = active ? "#60a5fa" : "#9fb0cc";
  return `<th data-sort="${col.key}"
    style="text-align:left; color:${color}; cursor:pointer;
    padding:6px 4px; user-select:none;">${col.label}${arrow}</th>`;
}

function _renderSectorTable() {
  const rows = _sectorSorted();
  let html = `<table style="width:100%; border-collapse:collapse; font-size:12px;">
    <thead><tr style="border-bottom:1px solid rgba(255,255,255,.1);">
      ${_SECTOR_COLUMNS.map(_secHeaderCell).join("")}
    </tr></thead><tbody>`;
  rows.forEach(r => {
    const rel = _sectorRowReliability(r.n_setups);
    html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05);">
      <td style="padding:6px 4px;"><b>${r.sector || "Unknown"}</b></td>
      <td style="padding:6px 4px;">${r.n_symbols}</td>
      <td style="padding:6px 4px;">
        <span class="rel-pill ${rel}">${r.n_setups ?? 0}</span>
      </td>
      <td style="padding:6px 4px;">${r.n_triggered ?? 0}</td>
      <td style="padding:6px 4px;">${_secPct(r.p_trigger)}</td>
      <td style="padding:6px 4px;">${_secPct(r.p_1r_given_trigger)}</td>
      <td style="padding:6px 4px;">${_secPct(r.p_2r_given_trigger)}</td>
      <td style="padding:6px 4px;">${_secPct(r.p_3r_given_trigger)}</td>
      <td style="padding:6px 4px;">${_secNum(r.median_mfe_r)}</td>
      <td style="padding:6px 4px;">${_secNum(r.median_mae_r)}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  html += `<p style="color:#7f8da9; font-size:11px; margin-top:10px;">
    Pooled across all cached symbols in each sector.
    Reliability: <span class="rel-pill rel-strong">≥30</span> strong ·
    <span class="rel-pill rel-mod">15-29</span> moderate ·
    <span class="rel-pill rel-thin">1-14</span> thin.
    Click headers to sort.
  </p>`;
  return html;
}

async function loadResearchSectors() {
  const box = document.getElementById("researchSectorBox");
  const badge = document.getElementById("researchSectorBadge");
  if (!box) return;
  box.innerHTML = "<p>Loading...</p>";
  try {
    const data = await api("/api/research-sector");
    _sectorRows = data.sectors || [];
    if (!_sectorRows.length) {
      box.innerHTML = "<p>No sector data yet. Warm the cache first.</p>";
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) {
      badge.textContent =
        `${data.n_sectors} sectors · ${data.n_symbols_cached} symbols`;
    }
    box.innerHTML = _renderSectorTable();
    _bindSectorEvents(box);
  } catch (e) {
    box.innerHTML = `<p>Sector view error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

function _bindSectorEvents(box) {
  box.querySelectorAll("th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (_sectorSortKey === key) {
        _sectorSortDir = -_sectorSortDir;
      } else {
        _sectorSortKey = key;
        _sectorSortDir = -1;
      }
      box.innerHTML = _renderSectorTable();
      _bindSectorEvents(box);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshResearchSector");
  if (btn) btn.addEventListener("click", loadResearchSectors);
});