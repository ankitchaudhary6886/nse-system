// Research Cockpit — per-symbol deep dive.

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

function _renderCandleBlock(data) {
  const cs = data.candle_stats || {};
  const currentType = data.current_setup && data.current_setup.mother_type;
  const keys = Object.keys(cs);
  if (!keys.length) return "";
  // sort by n_setups desc
  keys.sort((a, b) => (cs[b].n_setups || 0) - (cs[a].n_setups || 0));

  let html = `<h4 style="margin:14px 0 8px; font-size:13px;">🕯️ Candle behaviour (mother-bar classification)</h4>`;
  if (currentType) {
    html += `<div class="level" style="padding:8px 12px; border-left:3px solid #60a5fa;">
      <span>Today's mother bar</span>
      <strong>${currentType}</strong>
    </div>`;
  }
  html += `<table style="width:100%; border-collapse:collapse; font-size:12px;">
    <thead><tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
      <th style="padding:6px 4px;">Type</th>
      <th style="padding:6px 4px;">n</th>
      <th style="padding:6px 4px;">trig</th>
      <th style="padding:6px 4px;">P+1R</th>
      <th style="padding:6px 4px;">P+2R</th>
      <th style="padding:6px 4px;">P+3R</th>
      <th style="padding:6px 4px;">MFE</th>
      <th style="padding:6px 4px;">MAE</th>
    </tr></thead><tbody>`;
  keys.forEach(k => {
    const s = cs[k];
    const n = s.n_setups || 0;
    const isCurrent = (k === currentType);
    const rowStyle = isCurrent
      ? "border-bottom:1px solid rgba(255,255,255,.05); background:rgba(96,165,250,.10);"
      : "border-bottom:1px solid rgba(255,255,255,.05);";
    const relClass = n >= 10 ? "rel-strong" : n >= 5 ? "rel-mod" : "rel-thin";
    html += `<tr style="${rowStyle}">
      <td style="padding:6px 4px;"><b>${k}</b>${isCurrent ? " ←" : ""}</td>
      <td style="padding:6px 4px;"><span class="rel-pill ${relClass}">${n}</span></td>
      <td style="padding:6px 4px;">${s.n_triggered || 0}</td>
      <td style="padding:6px 4px;">${_pctStr(s.p_1r)}</td>
      <td style="padding:6px 4px;">${_pctStr(s.p_2r)}</td>
      <td style="padding:6px 4px;">${_pctStr(s.p_3r)}</td>
      <td style="padding:6px 4px;">${_num(s.median_mfe_r)}R</td>
      <td style="padding:6px 4px;">${_num(s.median_mae_r)}R</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  return html;
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
    if (cs.mother_type) {
      html += _researchRow("Mother bar",
        `${cs.mother_type} · body ${cs.mother_body_ratio} · range ${cs.mother_range_atr}x ATR`);
    }
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

  html += `<div class="level" style="padding:8px 12px;">
    <span>Hit rate (given trigger)</span>
    <strong>
      +1R ${_pctStr(h.p_1r_given_trigger)} · +2R ${_pctStr(h.p_2r_given_trigger)} · +3R ${_pctStr(h.p_3r_given_trigger)} · +4R ${_pctStr(h.p_4r_given_trigger)}
    </strong>
  </div>`;

  html += `<div class="level" style="padding:8px 12px;">
    <span>Median bars to level</span>
    <strong>
      +1R ${_num(h.median_bars_to_1r, 0)} · +2R ${_num(h.median_bars_to_2r, 0)} · +3R ${_num(h.median_bars_to_3r, 0)} · +4R ${_num(h.median_bars_to_4r, 0)}
    </strong>
  </div>`;

  html += `<div class="level" style="padding:8px 12px;">
    <span>MFE in R</span>
    <strong>p5 ${_num(h.p5_mfe_r)} · median ${_num(h.median_mfe_r)} · p95 ${_num(h.p95_mfe_r)}</strong>
  </div>`;

  html += `<div class="level" style="padding:8px 12px;">
    <span>MAE in R</span>
    <strong>p5 ${_num(h.p5_mae_r)} · median ${_num(h.median_mae_r)} · p95 ${_num(h.p95_mae_r)}</strong>
  </div>`;

  if (h.outcome_mix) {
    const parts = Object.entries(h.outcome_mix).map(
      ([k, v]) => `${k}:${v}`).join(" · ");
    html += _researchRow("Outcome mix", parts);
  }

  // Candle block
  html += _renderCandleBlock(data);

  if (data.recent_setups && data.recent_setups.length) {
    html += `<h4 style="margin:14px 0 8px; font-size:13px;">Recent historical setups</h4>`;
    html += `<table style="width:100%; border-collapse:collapse; font-size:12px;">
      <thead><tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
        <th style="padding:6px 4px;">Signal</th>
        <th style="padding:6px 4px;">Entry</th>
        <th style="padding:6px 4px;">Mother</th>
        <th style="padding:6px 4px;">Trig</th>
        <th style="padding:6px 4px;">MFE</th>
        <th style="padding:6px 4px;">MAE</th>
        <th style="padding:6px 4px;">Outcome</th>
      </tr></thead><tbody>`;
    data.recent_setups.forEach(s => {
      html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05);">
        <td style="padding:6px 4px;">${s.signal_date}</td>
        <td style="padding:6px 4px;">${s.entry}</td>
        <td style="padding:6px 4px;">${s.mother_type || "—"}</td>
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

window.loadResearch = loadResearch;