// Strategy Runner — Run, Edit, and Backtest buttons on each strategy card.

async function loadStrategyListFor(kind) {
  const container = document.getElementById(kind + "StrategyList");
  const badge = document.getElementById(kind + "StrategyBadge");
  if (!container) return;
  container.innerHTML = "<p>Loading strategies...</p>";
  try {
    const data = await api("/api/strategies");
    const strategies = data.strategies || {};
    const matching = Object.entries(strategies)
      .map(([key, s]) => ({ key, s }))
      .filter(x => (x.s.type || "").toLowerCase() === kind);

    if (!matching.length) {
      container.innerHTML = `<p>No ${kind} strategies defined yet.</p>`;
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${matching.length} strategies`;
    container.innerHTML = "";
    for (const { key, s } of matching) {
      container.appendChild(_buildStrategyCard(key, s, kind));
    }
  } catch (e) {
    container.innerHTML = `<p>Error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

function _buildStrategyCard(key, strategy, kind) {
  const wrap = document.createElement("div");
  wrap.className = "strategy-block";
  const condSummary = (strategy.conditions || [])
    .map(c => `${c.field} ${c.op} ${c.value}`)
    .join(" · ");
  const safeKey = _safeId(key);
  wrap.innerHTML = `
    <div class="strategy-head">
      <div>
        <strong>${strategy.name || key}</strong>
        <div class="strategy-desc">${strategy.description || ""}</div>
        <div class="strategy-cond">${condSummary}</div>
      </div>
      <div style="display:flex; gap:8px;">
        <button class="strategy-bt-btn" style="padding:8px 14px; border-radius:10px; background:rgba(167,139,250,.12); color:#a78bfa; border:1px solid rgba(167,139,250,.35); font-weight:700; cursor:pointer; font-size:12px;">Backtest</button>
        <button class="strategy-edit-btn" style="padding:8px 14px; border-radius:10px; background:rgba(255,255,255,.05); color:#9fb0cc; border:1px solid rgba(255,255,255,.15); font-weight:700; cursor:pointer; font-size:12px;">Edit</button>
        <button class="strategy-run-btn">Run</button>
      </div>
    </div>
    <div class="strategy-picks" id="strat-picks-${safeKey}">
      <p class="strategy-hint">Press <b>Run</b> to compute today's picks or <b>Backtest</b> for history.</p>
    </div>`;

  const runBtn = wrap.querySelector(".strategy-run-btn");
  runBtn.addEventListener("click", async () => {
    const box = document.getElementById("strat-picks-" + safeKey);
    runBtn.textContent = "Running...";
    runBtn.disabled = true;
    box.innerHTML = "<p>Computing across universe...</p>";
    try {
      const r = await api(`/api/strategies/${encodeURIComponent(key)}/run?limit=30`);
      if (r.error) {
        box.innerHTML = `<p class="strategy-error">${r.error}</p>`;
      } else {
        box.innerHTML = _renderStrategyPicks(r);
        _bindPickCards(box);
      }
    } catch (e) {
      box.innerHTML = `<p class="strategy-error">${e.message}</p>`;
    }
    runBtn.textContent = "Run";
    runBtn.disabled = false;
  });

  wrap.querySelector(".strategy-edit-btn").addEventListener("click", () => {
    if (window.openStrategyEditor) window.openStrategyEditor(key);
  });

  wrap.querySelector(".strategy-bt-btn").addEventListener("click", () => {
    openBacktestModal(key, strategy.name || key);
  });

  return wrap;
}

function _safeId(s) {
  return String(s).replace(/[^A-Za-z0-9_-]/g, "_");
}

function _renderStrategyPicks(r) {
  if (!r.picks || !r.picks.length) {
    return `<p class="strategy-hint">0 of ${r.n_symbols_checked} passed — try loosening conditions.</p>`;
  }
  let html = `<div class="strategy-hint">${r.n_passed} passed of ${r.n_symbols_checked} checked · run at ${r.run_at}</div>`;
  html += `<table class="strategy-table">
    <thead><tr>
      <th>Symbol</th><th>Sector</th><th>Score</th><th>Close</th><th>Off 52wHi</th><th>Checks</th>
    </tr></thead><tbody>`;
  r.picks.forEach(p => {
    const off = p.distance_from_52w_high != null
      ? (p.distance_from_52w_high * 100).toFixed(1) + "%" : "—";
    const close = p.close != null ? Number(p.close).toFixed(2) : "—";
    const checks = (p.checks || []).map(c =>
      `<span class="${c.ok ? 'chk-ok' : 'chk-fail'}" title="${c.field} ${c.op} ${c.want} (got ${c.got})">${c.ok ? "✓" : "✗"}</span>`
    ).join(" ");
    html += `<tr class="strategy-row" data-sym="${p.symbol}">
      <td><b>${p.symbol}</b></td>
      <td>${p.sector || "—"}</td>
      <td>${p.score != null ? p.score.toFixed(3) : "—"}</td>
      <td>${close}</td>
      <td>${off}</td>
      <td>${checks}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  return html;
}

function _bindPickCards(box) {
  box.querySelectorAll(".strategy-row").forEach(row => {
    row.addEventListener("click", () => {
      const sym = row.dataset.sym;
      if (!sym) return;
      setView("research");
      loadSymbol(sym);
      if (window.loadResearch) setTimeout(() => window.loadResearch(sym), 500);
    });
  });
}

// ============================================================
// Backtest Modal
// ============================================================
function _ensureBacktestModal() {
  let root = document.getElementById("backtestRoot");
  if (root) return root;
  root = document.createElement("div");
  root.id = "backtestRoot";
  root.style.cssText = `
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.7); z-index: 9999;
    overflow-y: auto; padding: 24px;
  `;
  root.innerHTML = `
    <div style="max-width: 960px; margin: 0 auto;
      background: #0d1220; border: 1px solid rgba(255,255,255,.15);
      border-radius: 16px; padding: 22px; color: #edf3ff;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h2 id="btTitle" style="margin:0; font-size:20px;">Backtest</h2>
        <button id="btClose" style="background:none; border:none; color:#9fb0cc; font-size:22px; cursor:pointer;">×</button>
      </div>
      <div id="btBody"><p>Running backtest... this may take 30-90s the first time.</p></div>
    </div>`;
  document.body.appendChild(root);
  root.addEventListener("click", (e) => { if (e.target === root) _closeBacktest(); });
  document.getElementById("btClose").addEventListener("click", _closeBacktest);
  return root;
}

function _closeBacktest() {
  const r = document.getElementById("backtestRoot");
  if (r) r.style.display = "none";
}

async function openBacktestModal(key, displayName) {
  _ensureBacktestModal();
  const root = document.getElementById("backtestRoot");
  root.style.display = "block";
  document.getElementById("btTitle").textContent = "Backtest: " + (displayName || key);
  const body = document.getElementById("btBody");
  body.innerHTML = "<p>Running backtest... this may take 30-90s the first time (cached after).</p>";
  try {
    const r = await api(`/api/strategies/${encodeURIComponent(key)}/backtest?years=2&step=5&universe_limit=150&refresh=false`);
    if (r.error) {
      body.innerHTML = `<p style="color:#fb7185;">${r.error}</p>`;
      return;
    }
    body.innerHTML = _renderBacktestResult(r);
  } catch (e) {
    body.innerHTML = `<p style="color:#fb7185;">Backtest error: ${e.message}</p>`;
  }
}

function _renderBacktestResult(r) {
  const wr = r.win_rate != null ? (r.win_rate * 100).toFixed(1) + "%" : "—";
  const hitColor = (r.win_rate || 0) >= 0.45 ? "#34d399"
                 : (r.win_rate || 0) >= 0.35 ? "#fbbf24"
                 : "#fb7185";
  const retColor = r.total_return_pct >= 0 ? "#34d399" : "#fb7185";

  let html = `
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-bottom:16px;">
      <div class="kcard"><div class="ktitle">Signals</div><div class="kvalue">${r.n_signals}</div><div class="ksub">${r.n_wins}W / ${r.n_losses}L / ${r.n_timeouts}T</div></div>
      <div class="kcard"><div class="ktitle">Win rate</div><div class="kvalue" style="color:${hitColor}">${wr}</div><div class="ksub">graded only</div></div>
      <div class="kcard"><div class="ktitle">Avg return</div><div class="kvalue" style="color:${retColor}">${r.avg_return_pct >= 0 ? "+" : ""}${r.avg_return_pct}%</div><div class="ksub">per trade</div></div>
      <div class="kcard"><div class="ktitle">Total return</div><div class="kvalue" style="color:${retColor}">${r.total_return_pct >= 0 ? "+" : ""}${r.total_return_pct}%</div><div class="ksub">max DD ${r.max_drawdown_pct}%</div></div>
    </div>
    <div style="font-size:12px; color:#7f8da9; margin-bottom:14px;">
      ${r.years}y · step ${r.step} · ${r.n_symbols} symbols · evaluated ${r.n_evaluated} points · entry next open · stop ${(r.stop_pct*100).toFixed(1)}% · target ${r.target_r}R · hold ${r.hold_bars}b · cached ${r._cached_at || r.run_at}
    </div>
  `;

  // Recent signals table
  if (r.recent_signals && r.recent_signals.length) {
    html += `<h3 style="margin:14px 0 8px; font-size:14px;">Recent signals (last 30)</h3>`;
    html += `<div style="max-height:320px; overflow-y:auto;"><table class="strategy-table">
      <thead><tr>
        <th>Signal</th><th>Symbol</th><th>Entry</th><th>Exit</th><th>Outcome</th><th>Return %</th><th>Bars</th>
      </tr></thead><tbody>`;
    r.recent_signals.slice().reverse().forEach(s => {
      const outClass = s.outcome === "WIN" ? "chk-ok"
                     : s.outcome === "LOSS" ? "chk-fail" : "";
      const rc = s.return_pct >= 0 ? "#34d399" : "#fb7185";
      html += `<tr style="cursor:pointer;" onclick="window.jumpResearch && window.jumpResearch('${s.symbol}')">
        <td>${s.signal_date}</td>
        <td><b>${s.symbol}</b></td>
        <td>₹${s.entry_price}</td>
        <td>₹${s.exit_price}</td>
        <td><span class="${outClass}">${s.outcome}</span></td>
        <td style="color:${rc}">${s.return_pct >= 0 ? "+" : ""}${s.return_pct}%</td>
        <td>${s.bars_held}</td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
  } else {
    html += `<p>No signals generated in this window.</p>`;
  }

  return html;
}

// ============================================================
// Init
// ============================================================
async function seedStrategies() {
  try {
    await api("/api/strategies/seed", { method: "POST" });
    await Promise.all([
      loadStrategyListFor("fundamental"),
      loadStrategyListFor("swing"),
    ]);
  } catch (e) {
    console.error("Seed failed:", e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  seedStrategies().then(() => {
    loadStrategyListFor("fundamental");
    loadStrategyListFor("swing");
  });
  const rb = document.getElementById("refreshBtn");
  if (rb) {
    rb.addEventListener("click", () => {
      loadStrategyListFor("fundamental");
      loadStrategyListFor("swing");
    });
  }
});