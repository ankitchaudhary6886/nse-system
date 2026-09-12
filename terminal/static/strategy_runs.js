// Strategy Runs panel — reads /api/strategy-runs and /api/strategy-summary.
// Renders a table of walk-forward sweeps.

async function loadStrategyRuns() {
  const box = document.getElementById("strategyRunsBox");
  const badge = document.getElementById("strategyRunsBadge");
  if (!box) return;
  try {
    const runsData = await api("/api/strategy-runs?n=15");
    const summaryData = await api("/api/strategy-summary");
    const runs = runsData.runs || [];
    const summary = summaryData.summary || [];
    if (!runs.length) {
      box.innerHTML = "<p>No strategy runs logged yet.</p>";
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${runs.length} runs`;

    let html = `<table style="width:100%; border-collapse:collapse; font-size:12px;">
      <thead>
        <tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
          <th style="padding:6px 4px;">Run</th>
          <th style="padding:6px 4px;">R</th>
          <th style="padding:6px 4px;">Yrs</th>
          <th style="padding:6px 4px;">N</th>
          <th style="padding:6px 4px;">WR</th>
          <th style="padding:6px 4px;">PF</th>
          <th style="padding:6px 4px;">Exp</th>
          <th style="padding:6px 4px;">Ret</th>
          <th style="padding:6px 4px;">DD</th>
          <th style="padding:6px 4px;">Verdict</th>
        </tr>
      </thead>
      <tbody>`;
    runs.forEach(r => {
      const vClass = (r.verdict || "").includes("STRONG") ? "WIN" :
                     (r.verdict || "").includes("SOLID") ? "OPEN" :
                     (r.verdict || "").includes("NO EDGE") ? "LOSS" : "PENDING";
      html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05);">
        <td style="padding:6px 4px; color:#7f8da9;">${(r.run_at || "").slice(5, 16)}</td>
        <td style="padding:6px 4px;">${r.target_r ?? "—"}</td>
        <td style="padding:6px 4px;">${r.years ?? "—"}</td>
        <td style="padding:6px 4px;">${r.trades ?? "—"}</td>
        <td style="padding:6px 4px;">${r.win_rate != null ? (r.win_rate * 100).toFixed(1) + "%" : "—"}</td>
        <td style="padding:6px 4px;"><b>${r.pf != null ? r.pf.toFixed(2) : "—"}</b></td>
        <td style="padding:6px 4px;">${r.expectancy_r != null ? (r.expectancy_r >= 0 ? "+" : "") + r.expectancy_r.toFixed(3) + "R" : "—"}</td>
        <td style="padding:6px 4px;">${r.total_return != null ? ((r.total_return >= 0 ? "+" : "") + (r.total_return * 100).toFixed(1) + "%") : "—"}</td>
        <td style="padding:6px 4px;">${r.max_dd != null ? (r.max_dd * 100).toFixed(1) + "%" : "—"}</td>
        <td style="padding:6px 4px;"><span class="outcome ${vClass}">${r.verdict || ""}</span></td>
      </tr>`;
    });
    html += `</tbody></table>`;

    if (summary.length) {
      html += `<h4 style="margin:16px 0 8px; font-size:13px;">Summary by target R</h4>
        <table style="width:100%; border-collapse:collapse; font-size:12px;">
          <thead>
            <tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
              <th style="padding:6px 4px;">Target R</th>
              <th style="padding:6px 4px;">Runs</th>
              <th style="padding:6px 4px;">Trades</th>
              <th style="padding:6px 4px;">Avg PF</th>
              <th style="padding:6px 4px;">Avg WR</th>
              <th style="padding:6px 4px;">Avg Exp</th>
              <th style="padding:6px 4px;">Avg DD</th>
            </tr>
          </thead>
          <tbody>`;
      summary.forEach(s => {
        html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05);">
          <td style="padding:6px 4px;">${s.target_r}</td>
          <td style="padding:6px 4px;">${s.runs}</td>
          <td style="padding:6px 4px;">${s.total_trades}</td>
          <td style="padding:6px 4px;"><b>${s.avg_pf != null ? s.avg_pf.toFixed(2) : "—"}</b></td>
          <td style="padding:6px 4px;">${s.avg_wr != null ? (s.avg_wr * 100).toFixed(1) + "%" : "—"}</td>
          <td style="padding:6px 4px;">${s.avg_exp != null ? (s.avg_exp >= 0 ? "+" : "") + s.avg_exp.toFixed(3) + "R" : "—"}</td>
          <td style="padding:6px 4px;">${s.avg_dd != null ? (s.avg_dd * 100).toFixed(1) + "%" : "—"}</td>
        </tr>`;
      });
      html += `</tbody></table>`;
    }

    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<p>Strategy runs error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadStrategyRuns();
  const btn = document.getElementById("refreshBtn");
  if (btn) {
    btn.addEventListener("click", loadStrategyRuns);
  }
});