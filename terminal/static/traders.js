// Traders — one page per famous trader. Each shows methods + signals.

let _tradersCache = null;
let _currentTraderSlug = null;

async function loadTradersIndex() {
  const box = document.getElementById("tradersIndex");
  if (!box) return;
  box.innerHTML = "<p>Loading traders...</p>";
  try {
    const data = await api("/api/traders");
    _tradersCache = data.traders || [];
    if (!_tradersCache.length) {
      box.innerHTML = "<p>No traders registered yet.</p>";
      return;
    }
    // Sidebar of traders + main panel
    let html = `<div class="traders-layout">
      <div class="traders-sidebar">`;
    _tradersCache.forEach((t, idx) => {
      const cls = idx === 0 ? "trader-tab active" : "trader-tab";
      html += `<button class="${cls}" data-slug="${t.slug}">
        <strong>${t.name}</strong>
        <span class="trader-meta">${t.pillar.toUpperCase()} · ${t.methods.length} methods</span>
      </button>`;
    });
    html += `</div><div class="traders-main" id="traderMainPanel"></div></div>`;
    box.innerHTML = html;
    // Wire tabs
    box.querySelectorAll(".trader-tab").forEach(btn => {
      btn.addEventListener("click", () => {
        box.querySelectorAll(".trader-tab").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectTrader(btn.dataset.slug);
      });
    });
    // Load first
    selectTrader(_tradersCache[0].slug);
  } catch (e) {
    box.innerHTML = `<p>Error loading traders: ${e.message}</p>`;
  }
}

async function selectTrader(slug) {
  _currentTraderSlug = slug;
  const panel = document.getElementById("traderMainPanel");
  if (!panel) return;
  const t = (_tradersCache || []).find(x => x.slug === slug);
  if (!t) { panel.innerHTML = "<p>Trader not found.</p>"; return; }

  panel.innerHTML = `
    <div class="trader-header">
      <div>
        <h2 style="margin:0;">${t.name}</h2>
        <p class="trader-source">${t.source || ""}</p>
        <div class="trader-pillar">Pillar: <b>${t.pillar.toUpperCase()}</b></div>
      </div>
      <button id="traderScanBtn" class="strategy-run-btn">Run Scan (all methods)</button>
    </div>
    <div id="traderMethods">
      <h3 style="margin-top:18px; font-size:14px;">Methods (${t.methods.length})</h3>
      <table class="strategy-table">
        <thead><tr>
          <th>Method</th><th>Direction</th><th>Description</th>
        </tr></thead>
        <tbody>
        ${t.methods.map(m => `<tr>
          <td><b>${m.name}</b></td>
          <td>${m.direction}</td>
          <td style="color:#9fb0cc;">${m.description || ""}</td>
        </tr>`).join("")}
        </tbody>
      </table>
    </div>
    <div id="traderSignals" style="margin-top:22px;">
      <p class="strategy-hint">Press <b>Run Scan</b> to compute signals across the universe.</p>
    </div>
  `;
  const btn = document.getElementById("traderScanBtn");
  if (btn) btn.addEventListener("click", () => runTraderScan(slug));
}

async function runTraderScan(slug) {
  const btn = document.getElementById("traderScanBtn");
  const box = document.getElementById("traderSignals");
  if (!box) return;
  if (btn) { btn.textContent = "Scanning..."; btn.disabled = true; }
  box.innerHTML = `<p>Scanning the band universe. This may take 30-60s...</p>`;
  try {
    const r = await api(`/api/traders/${encodeURIComponent(slug)}/scan?limit=800`);
    if (r.error) {
      box.innerHTML = `<p class="strategy-error">${r.error}</p>`;
    } else {
      box.innerHTML = _renderTraderSignals(r);
      _bindTraderSignalRows(box);
    }
  } catch (e) {
    box.innerHTML = `<p class="strategy-error">${e.message}</p>`;
  }
  if (btn) { btn.textContent = "Run Scan (all methods)"; btn.disabled = false; }
}

function _renderTraderSignals(r) {
  const sigs = r.signals || [];
  if (!sigs.length) {
    return `<h3 style="font-size:14px;">Signals (0)</h3>
      <p class="strategy-hint">No signals across the universe today.</p>`;
  }
  // Group by method
  const byMethod = {};
  sigs.forEach(s => {
    byMethod[s.method] = byMethod[s.method] || [];
    byMethod[s.method].push(s);
  });
  const methodOrder = Object.entries(byMethod)
    .sort((a, b) => b[1].length - a[1].length);

  let html = `<h3 style="font-size:14px;">Signals (${sigs.length})</h3>`;
  methodOrder.forEach(([method, arr]) => {
    html += `<h4 style="margin:14px 0 6px; font-size:13px; color:#9fb0cc;">
      ${method.replace(/_/g, " ")} · ${arr.length} signals
    </h4>
    <table class="strategy-table">
      <thead><tr>
        <th>Symbol</th><th>Direction</th><th>Order</th>
        <th>Entry</th><th>Stop</th><th>Confidence</th><th>Notes</th>
      </tr></thead>
      <tbody>
      ${arr.slice(0, 40).map(s => {
        const dirCls = s.direction === "BULLISH" ? "chk-ok"
                    : s.direction === "BEARISH" ? "chk-fail" : "";
        const conf = s.confidence || "—";
        const confCls = conf === "HIGH" ? "chk-ok"
                     : conf === "MED" ? "" : "chk-fail";
        const entry = s.entry != null ? Number(s.entry).toFixed(2) : "—";
        const stop = s.stop != null ? Number(s.stop).toFixed(2) : "—";
        return `<tr class="strategy-row" data-sym="${s.symbol}">
          <td><b>${s.symbol}</b></td>
          <td><span class="${dirCls}">${s.direction}</span></td>
          <td>${s.signal_type || "—"}</td>
          <td>${entry}</td>
          <td>${stop}</td>
          <td><span class="${confCls}">${conf}</span></td>
          <td style="color:#9fb0cc; font-size:11px;">${s.notes || ""}</td>
        </tr>`;
      }).join("")}
      </tbody>
    </table>`;
  });
  return html;
}

function _bindTraderSignalRows(box) {
  box.querySelectorAll(".strategy-row").forEach(row => {
    row.addEventListener("click", () => {
      const sym = row.dataset.sym;
      if (!sym) return;
      setView("research");
      loadSymbol(sym);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const rb = document.getElementById("refreshBtn");
  if (rb) {
    rb.addEventListener("click", () => {
      // If on Traders view, re-run the current trader scan
      const view = document.getElementById("view-traders");
      if (view && view.classList.contains("active-view") && _currentTraderSlug) {
        runTraderScan(_currentTraderSlug);
      }
    });
  }
});