// Strategy Runner — reads /api/strategies, runs a strategy, shows picks.
// Used on both Funda and Swing tabs.

async function loadStrategyListFor(kind) {
  const container = document.getElementById(kind + "StrategyList");
  const badge = document.getElementById(kind + "StrategyBadge");
  if (!container) return;
  container.innerHTML = "<p>Loading strategies...</p>";
  try {
    const data = await api("/api/strategies");
    const strategies = data.strategies || {};
    const matching = Object.values(strategies)
      .filter(s => (s.type || "").toLowerCase() === kind);
    if (!matching.length) {
      container.innerHTML = `<p>No ${kind} strategies defined yet.</p>`;
      if (badge) badge.textContent = "empty";
      return;
    }
    if (badge) badge.textContent = `${matching.length} strategies`;
    container.innerHTML = "";
    for (const s of matching) {
      const card = _buildStrategyCard(s, kind);
      container.appendChild(card);
    }
  } catch (e) {
    container.innerHTML = `<p>Error: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

function _buildStrategyCard(strategy, kind) {
  const wrap = document.createElement("div");
  wrap.className = "strategy-block";
  const condSummary = (strategy.conditions || [])
    .map(c => `${c.field} ${c.op} ${c.value}`)
    .join(" · ");
  wrap.innerHTML = `
    <div class="strategy-head">
      <div>
        <strong>${strategy.name}</strong>
        <div class="strategy-desc">${strategy.description || ""}</div>
        <div class="strategy-cond">${condSummary}</div>
      </div>
      <button class="strategy-run-btn" data-name="${strategy.name}">Run</button>
    </div>
    <div class="strategy-picks" id="strat-picks-${_safeId(strategy.name)}">
      <p class="strategy-hint">Press <b>Run</b> to compute today's picks.</p>
    </div>`;
  const btn = wrap.querySelector(".strategy-run-btn");
  btn.addEventListener("click", async () => {
    const box = document.getElementById("strat-picks-" + _safeId(strategy.name));
    btn.textContent = "Running...";
    btn.disabled = true;
    box.innerHTML = "<p>Computing across universe...</p>";
    try {
      const r = await api(`/api/strategies/${encodeURIComponent(strategy.name)}/run?limit=30`);
      if (r.error) {
        box.innerHTML = `<p class="strategy-error">${r.error}</p>`;
      } else {
        box.innerHTML = _renderStrategyPicks(r);
        _bindPickCards(box);
      }
    } catch (e) {
      box.innerHTML = `<p class="strategy-error">${e.message}</p>`;
    }
    btn.textContent = "Run";
    btn.disabled = false;
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
      ? (p.distance_from_52w_high * 100).toFixed(1) + "%"
      : "—";
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

async function seedStrategies() {
  try {
    await api("/api/strategies/seed", { method: "POST" });
    await Promise.all([
      loadStrategyListFor("fundamental"),
      loadStrategyListFor("swing"),
    ]);
  } catch (e) {
    alert("Seed failed: " + e.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Seed on first load if none exist, then render both tabs
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