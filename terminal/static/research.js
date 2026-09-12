// Research Cockpit — historical behaviour of setups for a symbol.
// Populates #researchBox in the Overview tab when a symbol is loaded.

function _researchRow(label, value, colour) {
  const col = colour || "#edf3ff";
  return `<div class="level" style="padding:8px 12px;">
    <span>${label}</span>
    <strong style="color:${col};">${value}</strong>
  </div>`;
}

function _pctStr(x) {
  if (x === null || x === undefined) return "—";
  return (x * 100).toFixed(0) + "%";
}

function _num(x, dp) {
  if (x === null || x === undefined) return "—";
  return Number(x).toFixed(dp === undefined ? 2 : dp);
}

function renderResearch(data) {
  const box = document.getElementById("researchBox");
  if (!box) return;
  if (data.error) {
    box.innerHTML = `<p>Research unavailable: ${data.error}</p>`;
    return;
  }
  const h = data.historical || {};
  let html = "";

  html += `<div style="font-size:12px; color:#7f8da9; margin-bottom:6px;">
    ${data.sector || "Unknown sector"} · as of ${data.as_of} ·
    close ${data.latest_close} · ${data.pct_from_52w_high}% below 52w high ·
    ${data.pct_from_52w_low}% above 52w low
  </div>`;

  if (data.current_setup) {
    const cs = data.current_setup;
    html += `<div class="level" style="padding:8px 12px; border-left:3px solid #34d399;">
      <span><b style="color:#34d399;">LIVE SETUP TODAY</b> — signal ${cs.signal_date}</span>
      <strong>entry ${cs.entry} · stop ${cs.stop} · 3R ${cs.target_3r}</strong>
    </div>`;
    html += _researchRow("Risk %", cs.risk_pct + "%");
    html += _researchRow("Pullback", cs.pullback_pct + "% over " + cs.pullback_days + "d");
    html += _researchRow("Impulse", cs.impulse_pct + "%");
    html += _researchRow("EMA zone", cs.ema_zone);
    html += _researchRow("Shape score", cs.shape_score + "/100");
  } else {
    html += `<div class="level" style="padding:8px 12px; border-left:3px solid #7f8da9;">
      <span>LIVE SETUP</span><strong>none triggered today</strong>
    </div>`;
  }

  html += `<h4 style="margin:14px 0 8px; font-size:13px;">Historical behaviour — ${h.n_setups || 0} setups over ${data.history_years}y (step ${data.step})</h4>`;

  if (!h.n_setups) {
    html += `<p>No historical setups found on this symbol.</p>`;
    box.innerHTML = html;
    return;
  }

  html += _researchRow("Triggered",
    `${h.n_triggered} of ${h.n_setups} (P=${_pctStr(h.p_trigger)})`);

  const p1 = h.p_1r_given_trigger;
  const p2 = h.p_2r_given_trigger;
  const p3 = h.p_3r_given_trigger;
  const p4 = h.p_4r_given_trigger;
  html += `<div class="level" style="padding:8px 12px;">
    <span>Hit rate (given trigger)</span>
    <strong>
      +1R ${_pctStr(p1)} · +2R ${_pctStr(p2)} · +3R ${_pctStr(p3)} · +4R ${_pctStr(p4)}
    </strong>
  </div>`;

  html += `<div class="level" style="padding:8px 12px;">
    <span>Median bars to level</span>
    <strong>
      +1R ${_num(h.median_bars_to_1r, 0)} · +2R ${_num(h.median_bars_to_2r, 0)} · +3R ${_num(h.median_bars_to_3r, 0)} · +4R ${_num(h.median_bars_to_4r, 0)}
    </strong>
  </div>`;

  html += `<div class="level" style="padding:8px 12px;">
    <span>MFE in R (favourable excursion)</span>
    <strong>p5 ${_num(h.p5_mfe_r)} · median ${_num(h.median_mfe_r)} · p95 ${_num(h.p95_mfe_r)}</strong>
  </div>`;

  html += `<div class="level" style="padding:8px 12px;">
    <span>MAE in R (adverse excursion)</span>
    <strong>p5 ${_num(h.p5_mae_r)} · median ${_num(h.median_mae_r)} · p95 ${_num(h.p95_mae_r)}</strong>
  </div>`;

  if (h.outcome_mix) {
    const parts = Object.entries(h.outcome_mix).map(
      ([k, v]) => `${k}:${v}`).join(" · ");
    html += _researchRow("Outcome mix", parts);
  }

  if (data.recent_setups && data.recent_setups.length) {
    html += `<h4 style="margin:14px 0 8px; font-size:13px;">Recent historical setups</h4>`;
    html += `<table style="width:100%; border-collapse:collapse; font-size:12px;">
      <thead><tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
        <th style="padding:6px 4px;">Signal</th>
        <th style="padding:6px 4px;">Entry</th>
        <th style="padding:6px 4px;">Trig</th>
        <th style="padding:6px 4px;">MFE</th>
        <th style="padding:6px 4px;">MAE</th>
        <th style="padding:6px 4px;">Outcome</th>
      </tr></thead><tbody>`;
    data.recent_setups.forEach(s => {
      html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05);">
        <td style="padding:6px 4px;">${s.signal_date}</td>
        <td style="padding:6px 4px;">${s.entry}</td>
        <td style="padding:6px 4px;">${s.triggered ? "✓" : "✗"}</td>
        <td style="padding:6px 4px;">${_num(s.mfe_r)}R</td>
        <td style="padding:6px 4px;">${_num(s.mae_r)}R</td>
        <td style="padding:6px 4px;">${s.outcome}</td>
      </tr>`;
    });
    html += `</tbody></table>`;
  }

  box.innerHTML = html;
}

async function loadResearch(symbol) {
  const box = document.getElementById("researchBox");
  if (!box) return;
  box.innerHTML = `<p>Computing (5-15s)...</p>`;
  try {
    const data = await api(`/api/research/${symbol}`);
    renderResearch(data);
  } catch (e) {
    box.innerHTML = `<p>Research error: ${e.message}</p>`;
  }
}

// Expose globally so app.js can call it
window.loadResearch = loadResearch;