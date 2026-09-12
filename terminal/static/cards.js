// Unified stock card + compare table renderers.
// One card component, used everywhere. One table renderer for compare.

function _ucEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderUnifiedCard(item) {
  // item: {symbol, setup, badges, subtitle, primary, secondary, note, onClick}
  const div = document.createElement("div");
  div.className = "unified-card";
  const setupBadge = item.setup
    ? '<span class="outcome WIN">🏄 LIVE</span>' : '';
  const extra = (item.badges || []).join(" ");
  let html = `<div class="uc-head">
    <span class="uc-symbol">${_ucEsc(item.symbol)}</span>
    ${setupBadge}${extra}
  </div>`;
  if (item.subtitle) {
    html += `<div class="uc-line">${item.subtitle}</div>`;
  }
  if (item.primary) {
    html += `<div class="uc-line">${item.primary}</div>`;
  }
  if (item.secondary) {
    html += `<div class="uc-line uc-dim">${item.secondary}</div>`;
  }
  if (item.note) {
    html += `<div class="uc-line uc-note">${item.note}</div>`;
  }
  div.innerHTML = html;
  div.addEventListener("click", item.onClick || (() => {
    if (window.setView && window.loadSymbol) {
      window.setView("research");
      window.loadSymbol(item.symbol);
    }
  }));
  return div;
}

// ------------------------------------------------------------
// Compare table
// ------------------------------------------------------------
function _cmpPct(v) {
  if (v == null) return "—";
  return (v * 100).toFixed(0) + "%";
}
function _cmpNum(v, dp) {
  if (v == null) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n.toFixed(dp == null ? 2 : dp);
}
function _cmpRs(v, dp) {
  if (v == null) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return "₹" + n.toFixed(dp == null ? 2 : dp);
}
function _cmpRow(label, values, isSection) {
  const cls = isSection ? "cmp-section" : "cmp-row";
  const style = isSection
    ? "background:rgba(96,165,250,.08); font-weight:700;"
    : "";
  return `<tr class="${cls}" style="${style}">
    <td class="cmp-label">${label}</td>
    ${values.map(v => `<td class="cmp-value">${v}</td>`).join("")}
  </tr>`;
}

function renderCompareTable(payload) {
  const box = document.getElementById("compareBox");
  if (!box) return;
  const rows = payload.rows || [];
  if (!rows.length) {
    box.innerHTML = "<p>No data.</p>";
    return;
  }
  const syms = rows.map(r => r.symbol);
  const header = `<tr class="cmp-header">
    <th class="cmp-label">Metric</th>
    ${syms.map(s => `<th class="cmp-value"><b>${_ucEsc(s)}</b></th>`).join("")}
  </tr>`;

  function colOf(fn) {
    return rows.map(r => fn(r));
  }

  let html = `<table class="cmp-table"><thead>${header}</thead><tbody>`;

  // Section: overview
  html += _cmpRow("Sector", colOf(r => r.sector || "—"), false);
  html += _cmpRow("Mcap", colOf(r => r.mcap_cr != null
    ? "₹" + Number(r.mcap_cr).toFixed(0) + " cr" : "—"), false);
  html += _cmpRow("Close", colOf(r => _cmpRs(r.close)), false);
  html += _cmpRow("1M / 3M perf",
    colOf(r => (r.perf1m != null || r.perf3m != null)
      ? `${_cmpNum(r.perf1m, 1)}% / ${_cmpNum(r.perf3m, 1)}%` : "—"),
    false);

  // Section: fundamentals
  html += _cmpRow("FUNDAMENTALS", syms.map(() => ""), true);
  html += _cmpRow("ROCE", colOf(r => r.roce != null
    ? Number(r.roce).toFixed(1) + "%" : "—"), false);
  html += _cmpRow("ROE", colOf(r => r.roe != null
    ? Number(r.roe).toFixed(1) + "%" : "—"), false);
  html += _cmpRow("PE", colOf(r => _cmpNum(r.pe, 1)), false);
  html += _cmpRow("D/E", colOf(r => _cmpNum(r.debt_to_equity, 2)), false);
  html += _cmpRow("Op margin", colOf(r => r.operating_margin != null
    ? Number(r.operating_margin).toFixed(1) + "%" : "—"), false);
  html += _cmpRow("Fund score", colOf(r => r.fund_score != null
    ? Number(r.fund_score).toFixed(0) : "—"), false);

  // Section: signal
  html += _cmpRow("SIGNAL", syms.map(() => ""), true);
  html += _cmpRow("P(WIN) meta", colOf(r => _cmpPct(r.p_win)), false);
  html += _cmpRow("Swing W-L",
    colOf(r => (r.swing_total > 0)
      ? `${r.swing_wins}W / ${r.swing_losses}L` : "—"), false);
  html += _cmpRow("Latest pattern",
    colOf(r => r.pattern
      ? `${r.pattern.replace(/_/g, " ")} ${r.pattern_direction} `
        + `(${r.pattern_status}, ${_cmpNum(r.pattern_confidence, 0)})`
      : "—"), false);
  html += _cmpRow("Live setup", colOf(r => {
    if (!r.live_setup) return "—";
    return `entry ₹${_cmpNum(r.live_entry)} · stop ₹${_cmpNum(r.live_stop)}`
      + (r.live_mother ? ` · ${r.live_mother}` : "");
  }), false);

  // Section: history
  html += _cmpRow("HISTORY (symbol)", syms.map(() => ""), true);
  html += _cmpRow("n setups / triggered",
    colOf(r => (r.hist_n_setups != null)
      ? `${r.hist_n_setups} / ${r.hist_n_triggered}`
      : "—"), false);
  html += _cmpRow("P(+1R) / P(+2R)",
    colOf(r => (r.hist_p_1r != null || r.hist_p_2r != null)
      ? `${_cmpPct(r.hist_p_1r)} / ${_cmpPct(r.hist_p_2r)}` : "—"), false);
  html += _cmpRow("MFE / MAE (R)",
    colOf(r => (r.hist_median_mfe_r != null || r.hist_median_mae_r != null)
      ? `${_cmpNum(r.hist_median_mfe_r)} / ${_cmpNum(r.hist_median_mae_r)}`
      : "—"), false);
  html += _cmpRow("Best candle (n)",
    colOf(r => r.best_candle
      ? `${r.best_candle} · P+2R ${_cmpPct(r.best_candle_p2r)}`
      : "—"), false);

  // Section: signature match
  html += _cmpRow("SIGNATURE MATCH", syms.map(() => ""), true);
  html += _cmpRow("P(+2R) from k nearest",
    colOf(r => r.sig_p_2r != null ? _cmpPct(r.sig_p_2r) : "—"), false);
  html += _cmpRow("k / pool size",
    colOf(r => (r.sig_matches != null || r.sig_pool != null)
      ? `${r.sig_matches || "—"} / ${r.sig_pool || "—"}` : "—"), false);

  html += `</tbody></table>`;
  box.innerHTML = html;
}

window.renderUnifiedCard = renderUnifiedCard;
window.renderCompareTable = renderCompareTable;