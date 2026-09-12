let chart = null, candleSeries = null, ema10 = null, ema20 = null, ema50 = null, ema200 = null;
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
}
function fmt(v, suffix = "") { return (v === null || v === undefined || Number.isNaN(v)) ? "—" : `${v}${suffix}`; }
function outcomeBadge(v) { return `<span class="outcome ${v || "PENDING"}">${v || "PENDING"}</span>`; }

// Remap legacy "overview" → "research" so external scripts don't break
function _normalizeView(name) {
  if (name === "overview") return "research";
  return name;
}

function setView(name) {
  name = _normalizeView(name);
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active-view"));
  const el = $("view-" + name);
  if (el) el.classList.add("active-view");
  document.querySelectorAll(".nav-btn").forEach(b => {
    b.classList.toggle("active", _normalizeView(b.dataset.view) === name);
  });
  const titles = {
    funda: "Funda — positional & long-term",
    swing: "Swing — midcap / smallcap momentum",
    research: "Research — analysis & pattern lab",
    ledger: "Ledger — track record",
    system: "System — health & config",
  };
  const t = $("viewTitle");
  if (t) t.textContent = titles[name] || "NSE Intelligence";
  const subtitle = $("viewSubtitle");
  if (subtitle) {
    const subs = {
      funda: "Quality names in market downturns. Hold months to years.",
      swing: "Momentum setups in uptrending markets. Trade days to weeks.",
      research: "Deep-dive any symbol. Historical behaviour of similar setups.",
      ledger: "Your strategy's real track record, walk-forward validation.",
      system: "Infrastructure health, data freshness, deployment checks.",
    };
    subtitle.textContent = subs[name] || "Gabani Stage-2 / VCP Pullback System";
  }
  if (name === "research" && chart) setTimeout(() => chart.timeScale().fitContent(), 50);
  if (name === "ledger") loadLedger();
  if (name === "research") loadPatterns();
  if (name === "system") loadDeployment();
}

async function loadHealth() {
  try {
    const h = await api("/api/health");
    const el = $("healthStatus");
    if (el) el.textContent = `${h.prices_rows.toLocaleString()} price rows`;
  } catch (e) { const el = $("healthStatus"); if (el) el.textContent = "Offline"; }
}

async function loadRegime() {
  const box = $("regimeBanner");
  if (!box) return;
  try {
    const r = await api("/api/regime");
    box.classList.remove("loading", "bull", "defensive");
    let regimeHtml = "";
    if (r.stance === "STRONG_BULL") { box.classList.add("bull"); regimeHtml = `🟢🟢 <strong>STRONG BULL</strong> — ${r.symbol} close ${r.index_close} > EMA10 ${r.ema10}. Size ×1.0`; }
    else if (r.stance === "BULL") { box.classList.add("bull"); regimeHtml = `🟢 <strong>BULL</strong> — ${r.symbol} close ${r.index_close} > EMA10 ${r.ema10}. Size ×1.0`; }
    else if (r.stance === "NEUTRAL") { regimeHtml = `🟡 <strong>NEUTRAL</strong> — ${r.symbol} close ${r.index_close} vs EMA10 ${r.ema10}. Size ×0.75`; }
    else if (r.stance === "WEAK") { box.classList.add("defensive"); regimeHtml = `🟠 <strong>WEAK</strong> — ${r.symbol} close ${r.index_close} < EMA10 ${r.ema10}. Size ×0.5, AW only`; }
    else if (r.stance === "CAPITULATION") { box.classList.add("defensive"); regimeHtml = `🔴 <strong>CAPITULATION</strong> — ${r.symbol} close ${r.index_close} < EMA10 ${r.ema10}. Size ×0.25, AW only`; }
    else { regimeHtml = `⚠️ Regime unavailable: ${r.error || ""}`; }
    let macroHtml = "";
    try {
      const m = await api("/api/macro");
      if (m && m.fii_net !== null && m.dii_net !== null) {
        const net = m.fii_net + m.dii_net;
        const icon = net >= 0 ? "🟢" : "🛑";
        macroHtml = `<div style="margin-top:8px; font-size:14px; opacity:0.9;">${icon} Smart Money Flow: FII ${m.fii_net > 0 ? "+" : ""}${m.fii_net.toFixed(0)}Cr / DII ${m.dii_net > 0 ? "+" : ""}${m.dii_net.toFixed(0)}Cr (Net: ${m.net_flow > 0 ? "+" : ""}${m.net_flow.toFixed(0)}Cr)</div>`;
      }
    } catch (e) {}
    box.innerHTML = regimeHtml + macroHtml;
  } catch (e) { box.classList.add("defensive"); box.innerHTML = "⚠️ Regime API unavailable."; }
}

// ============================================================
// Unified stock card — one layout used everywhere
// ============================================================
function renderUnifiedCard(item) {
  // item may have: symbol, sector, mcap_cr, fund_score, p_win,
  // setup flag, n_setups, p_1r, p_2r, median_mfe_r, notes
  const sym = item.symbol || "—";
  const sector = item.sector || "";
  const mcap = item.mcap_cr != null ? `₹${Number(item.mcap_cr).toFixed(0)}cr` : "";
  const fund = item.fund_score != null ? `Fund ${Number(item.fund_score).toFixed(0)}` : "";
  const pwin = item.p_win != null ? `P(WIN) ${(item.p_win * 100).toFixed(0)}%` : "";
  const setupBadge = item.setup ? `<span class="outcome WIN">LIVE SETUP</span>` : "";
  const n = item.n_setups;
  const nPill = n != null ? `<span class="rel-pill ${n>=10?"rel-strong":n>=5?"rel-mod":n>=1?"rel-thin":"rel-none"}">n=${n}</span>` : "";
  const hits = (item.p_1r != null || item.p_2r != null)
    ? `+1R ${item.p_1r != null ? (item.p_1r*100).toFixed(0)+"%" : "—"} · +2R ${item.p_2r != null ? (item.p_2r*100).toFixed(0)+"%" : "—"}`
    : "";
  const mfe = item.median_mfe_r != null ? `MFE ${Number(item.median_mfe_r).toFixed(2)}R` : "";
  const line1 = [sector, mcap, fund].filter(Boolean).join(" · ");
  const line2 = [pwin, hits, mfe, nPill].filter(Boolean).join(" · ");
  return `<div class="unified-card" data-sym="${sym}">
    <div class="uc-head">
      <span class="uc-symbol">${sym}</span>
      ${setupBadge}
    </div>
    ${line1 ? `<div class="uc-line">${line1}</div>` : ""}
    ${line2 ? `<div class="uc-line uc-dim">${line2}</div>` : ""}
    ${item.notes ? `<div class="uc-line uc-note">${item.notes}</div>` : ""}
  </div>`;
}

function _bindUnifiedCards(container) {
  container.querySelectorAll(".unified-card").forEach(card => {
    card.addEventListener("click", () => {
      const sym = card.dataset.sym;
      if (!sym) return;
      setView("research");
      loadSymbol(sym);
      if (window.loadResearch) setTimeout(() => window.loadResearch(sym), 500);
    });
  });
}

// ============================================================
// Progressive disclosure
// ============================================================
function _toggleDetails(targetId) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.classList.toggle("hidden");
}

// Global handler: any .toggle-btn with data-target toggles that panel
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".toggle-btn");
  if (btn) {
    e.preventDefault();
    const target = btn.dataset.target;
    if (target) _toggleDetails(target);
  }
});

// ============================================================
// Top Picks (featured, in Funda tab)
// ============================================================
async function loadTopPicks() {
  try {
    const data = await api("/api/toppicks");
    const box = $("picksList");
    if (!box) return;
    box.innerHTML = "";
    (data.picks || []).forEach(x => {
      const div = document.createElement("div");
      div.className = "stock-card";
      const del = x.delivery != null ? ` · 📦 ${(x.delivery * 100).toFixed(0)}` : "";
      div.innerHTML = `<strong>${x.symbol} ${x.setup ? '<span class="outcome WIN">🏄 LIVE SETUP</span>' : ""}</strong>
        <span>Composite ${(x.composite * 100).toFixed(0)} · 🧠 ${(x.p_win * 100).toFixed(0)}% · 🏦 ${x.accum.toFixed(2)}${del}</span>
        <span>${x.sector || "Unknown sector"} · sector RS ${(x.sector_rs * 100).toFixed(0)}</span>`;
      div.addEventListener("click", () => {
        setView("research");
        loadSymbol(x.symbol);
      });
      box.appendChild(div);
    });
  } catch (e) {}
}

// ============================================================
// Swing desk
// ============================================================
async function loadSwing() {
  const data = await api("/api/swing/signals");
  const tbody = $("swingTable");
  if (!tbody) return;
  tbody.innerHTML = "";
  const signals = data.signals || [];
  const score = data.scorecard || {};
  const ms = $("mSignals"); if (ms) ms.textContent = signals.length;
  const mw = $("mWinRate"); if (mw) mw.textContent = data.win_rate === null ? "—" : `${data.win_rate}%`;
  const mo = $("mOpen"); if (mo) mo.textContent = `${score.OPEN || 0} / ${score.PENDING || 0}`;
  for (const s of signals) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${s.date}</td>
      <td><strong>${s.symbol}</strong> ${s.p_win != null ? `<span class="outcome PENDING">🧠${(s.p_win * 100).toFixed(0)}%</span>` : ""} ${s.mode === "ALL_WEATHER" ? '<span class="outcome TIMEOUT">AW</span>' : ""}</td>
      <td>${fmt(s.trigger)}</td><td>${fmt(s.stop)}</td><td>${fmt(s.target)}</td>
      <td>${fmt(s.risk_pct, "%")}</td>
      <td>${s.pullback ? (s.pullback * 100).toFixed(1) + "%" : "—"}</td>
      <td>${s.impulse ? (s.impulse * 100).toFixed(1) + "%" : "—"}</td>
      <td>${s.ema_zone || "—"}</td>
      <td>${outcomeBadge(s.outcome)}</td>`;
    tr.addEventListener("click", () => { setView("research"); loadSymbol(s.symbol); });
    tbody.appendChild(tr);
  }
}

// ============================================================
// Patterns (Research tab)
// ============================================================
function dirBadge(d) {
  return d === "BULLISH" ? '<span class="outcome WIN">BULLISH</span>' : '<span class="outcome LOSS">BEARISH</span>';
}
function statusBadge(s) {
  if (s === "BREAKOUT") return '<span class="outcome WIN">BREAKOUT</span>';
  if (s === "READY") return '<span class="outcome OPEN">READY</span>';
  if (s === "BREAKDOWN") return '<span class="outcome LOSS">BREAKDOWN</span>';
  if (s === "WARNING") return '<span class="outcome TIMEOUT">WARNING</span>';
  return '<span class="outcome PENDING">FORMING</span>';
}
function gateBadge(g) {
  if (!g) return '<span class="outcome PENDING">HR n/a</span>';
  const cls = g.status === "ENABLED" ? "WIN" : (g.status === "DISABLED" ? "LOSS" : "TIMEOUT");
  return `<span class="outcome ${cls}">HR ${(g.win_rate * 100).toFixed(0)}% · ${g.status}</span>`;
}
function sauceLine(p) {
  const ss = (p && p.params && p.params.secret_sauce) || (p && p.secret_sauce) || {};
  const bits = [];
  if (ss.vcr != null) bits.push(`vcr ${Number(ss.vcr).toFixed(2)}`);
  if (ss.ret_std20 != null) bits.push(`vol-std ${(Number(ss.ret_std20) * 100).toFixed(1)}%`);
  if (ss.below52 != null) bits.push(`${(Number(ss.below52) * 100).toFixed(0)}% below 52w high`);
  return bits.join(" · ");
}

async function loadPatterns() {
  const list = $("patternList");
  const st = $("patternStatus");
  if (!list) return;
  try {
    const data = await api("/api/patterns/latest?limit=60");
    const rows = data.patterns || [];
    let gate = {};
    try { const gs = await api("/api/patterns/stats"); gate = gs.stats || {}; } catch (e) {}
    const vals = Object.values(gate);
    const en = vals.filter(v => v.status === "ENABLED").length;
    const pr = vals.filter(v => v.status === "PROVISIONAL").length;
    const di = vals.filter(v => v.status === "DISABLED").length;
    if (st) st.innerHTML = `<span>Stored formations</span><strong>${rows.length}${rows.length ? " · latest " + rows[0].date : ""} · gate: ${en} ON / ${pr} PROV / ${di} OFF</strong>`;
    list.innerHTML = "";
    if (!rows.length) {
      list.innerHTML = "<p>No stored patterns yet. Press Run Full Scan above (or wait for the 18:05 IST nightly job), then Refresh.</p>";
    } else {
      rows.forEach(p => {
        const div = document.createElement("div");
        div.className = "stock-card";
        const sauce = sauceLine(p);
        div.innerHTML = `<strong>${p.symbol} · ${(p.pattern || "").replace(/_/g, " ")}</strong>
          <span>${dirBadge(p.direction)} ${statusBadge(p.status)} ${gateBadge(gate[p.pattern])}</span>
          <span>Breakout ₹${p.breakout_level ?? "—"} · Stop ₹${p.stop_level ?? "—"} · Target ₹${p.target_level ?? "—"}</span>
          ${sauce ? `<span>${sauce}</span>` : ""}
          <span>${p.notes || ""}</span>`;
        div.addEventListener("click", () => { setView("research"); loadSymbol(p.symbol); });
        list.appendChild(div);
      });
    }
    // DTW template card
    let tmatch = [];
    try { const td = await api("/api/templates/latest?limit=12"); tmatch = td.matches || []; } catch (e) {}
    let tbox = $("templateBox");
    if (!tbox) {
      tbox = document.createElement("div");
      tbox.id = "templateBox";
      tbox.style.marginTop = "18px";
      list.parentElement.appendChild(tbox);
    }
    if (tmatch.length) {
      tbox.innerHTML = `<h3 style="margin:0 0 10px;font-size:15px;">🧬 DTW Shape Matches</h3>` +
        tmatch.map(m => `<div class="stock-card" data-sym="${m.symbol}" style="margin-bottom:8px;"><strong>${m.symbol} · ${(m.template || "").replace(/_/g, " ")}</strong><span>shape similarity ${m.similarity}% · ${m.date}</span></div>`).join("");
      tbox.querySelectorAll(".stock-card").forEach(card => {
        card.addEventListener("click", () => {
          setView("research");
          loadSymbol(card.dataset.sym);
        });
      });
    } else {
      tbox.innerHTML = `<h3 style="margin:0 0 10px;font-size:15px;">🧬 DTW Shape Matches</h3><p>No template matches stored yet.</p>`;
    }
  } catch (e) {
    if (st) st.innerHTML = `<span>Status</span><strong>pattern endpoint unavailable</strong>`;
    list.innerHTML = `<p>Pattern endpoint error: ${e.message}</p>`;
  }
}

async function runPatternScan() {
  const btn = $("runPatternScan");
  const st = $("patternStatus");
  if (btn) btn.textContent = "Scan queued…";
  try {
    await api("/api/patterns/scan", { method: "POST" });
    if (st) st.innerHTML = `<span>Status</span><strong>scan running in background (a few minutes) — click Refresh afterwards</strong>`;
    setTimeout(loadPatterns, 60000);
  } catch (e) {
    if (st) st.innerHTML = `<span>Status</span><strong>scan start failed: ${e.message}</strong>`;
  }
  if (btn) btn.textContent = "Run Full Scan";
}

// ============================================================
// Radar / Screener (kept for legacy use)
// ============================================================
function createRadarCard(item) {
  const div = document.createElement("div");
  div.className = "stock-card";
  div.innerHTML = `<strong>${item.symbol}</strong><span>1M ${fmt(item.perf1m, "%")} · 3M ${fmt(item.perf3m, "%")} · Vol ${fmt(item.relvol, "x")}</span><span>₹${fmt(item.mcap_cr)} cr mcap</span>${item.p_win != null ? `<span>🧠 P(WIN) ${(item.p_win * 100).toFixed(0)}%</span>` : ""}`;
  div.addEventListener("click", () => { setView("research"); loadSymbol(item.symbol); });
  return div;
}
async function loadRadar() {
  try {
    const data = await api("/api/radar");
    const mu = $("mUniverse"); if (mu) mu.textContent = data.total || "—";
    const g = data.groups || {};
    const m = $("radarMomentum"), v = $("radarVolume"), t = $("radarTurn");
    if (m) m.innerHTML = ""; if (v) v.innerHTML = ""; if (t) t.innerHTML = "";
    (g["Momentum"] || []).slice(0, 18).forEach(x => m && m.appendChild(createRadarCard(x)));
    (g["Volume Spike"] || []).slice(0, 18).forEach(x => v && v.appendChild(createRadarCard(x)));
    (g["Turnaround"] || []).slice(0, 18).forEach(x => t && t.appendChild(createRadarCard(x)));
  } catch (e) {}
}

// ============================================================
// Ledger
// ============================================================
async function loadLedger() {
  try {
    const stats = await api("/api/ledger/stats");
    const trades = await api("/api/ledger/trades");
    const box = $("ledgerStats");
    if (!box) return;
    if (!stats || stats.total_trades === 0) {
      box.innerHTML = "<p>No graded trades yet. Run swing scans daily to build history.</p>";
    } else {
      box.innerHTML = `
        <div class="level"><span>Total Trades</span><strong>${stats.total_trades}</strong></div>
        <div class="level"><span>Wins / Losses</span><strong>${stats.wins} / ${stats.losses}</strong></div>
        <div class="level"><span>Win Rate</span><strong>${stats.win_rate}%</strong></div>
        <div class="level"><span>Profit Factor</span><strong>${stats.profit_factor}</strong></div>
        <div class="level"><span>Expectancy</span><strong>${stats.expectancy_r} R</strong></div>
        <div class="level"><span>Total Return</span><strong>${stats.total_r} R</strong></div>
        <div class="level"><span>Max Drawdown</span><strong>${stats.max_drawdown_r} R</strong></div>`;
    }
    const tbody = $("ledgerTable");
    if (tbody) {
      tbody.innerHTML = "";
      (trades.trades || []).forEach(t => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${t.date}</td><td><strong>${t.symbol}</strong></td><td>${fmt(t.trigger)}</td><td>${fmt(t.stop)}</td><td>${fmt(t.target)}</td><td>${outcomeBadge(t.outcome)}</td>`;
        tr.addEventListener("click", () => { setView("research"); loadSymbol(t.symbol); });
        tbody.appendChild(tr);
      });
    }
  } catch (e) { const box = $("ledgerStats"); if (box) box.innerHTML = `<p>Error loading ledger: ${e.message}</p>`; }
}

// ============================================================
// Deployment (System tab)
// ============================================================
async function loadDeployment() {
  const box = $("deploymentBox");
  const badge = $("deploymentBadge");
  if (!box) return;
  try {
    const data = await api("/api/deployment-check");
    const checks = data.checks || [];
    const fails = data.fails || 0;
    if (badge) {
      badge.textContent = data.summary || "—";
      badge.className = fails === 0 ? "badge good" : "badge muted";
    }
    let html = `<div style="font-size:12px; color:#7f8da9; margin-bottom:8px;">${data.time || ""}</div>`;
    checks.forEach(c => {
      const icon = c.ok ? "✓" : "✗";
      const color = c.ok ? "#34d399" : "#fb7185";
      html += `<div class="level" style="padding:8px 12px;">
        <span style="color:${color}; font-weight:bold; min-width:20px; display:inline-block;">${icon}</span>
        <span style="flex:1; margin-left:8px;">${c.label}</span>
        <strong style="color:#9fb0cc; font-size:12px;">${c.detail || ""}</strong>
      </div>`;
    });
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<p>Deployment check unavailable: ${e.message}</p>`;
    if (badge) badge.textContent = "unavailable";
  }
}

// ============================================================
// Cockpit / Inspector (Research tab)
// ============================================================
function resetChart() {
  const el = $("chart");
  if (!el) return;
  el.innerHTML = "";
  chart = LightweightCharts.createChart(el, {
    layout: { background: { color: "transparent" }, textColor: "#9fb0cc" },
    grid: { vertLines: { color: "rgba(255,255,255,.05)" }, horzLines: { color: "rgba(255,255,255,.05)" } },
    rightPriceScale: { borderColor: "rgba(255,255,255,.08)" },
    timeScale: { borderColor: "rgba(255,255,255,.08)" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal }
  });
  candleSeries = chart.addCandlestickSeries({ upColor: "#34d399", downColor: "#fb7185", borderVisible: false, wickUpColor: "#34d399", wickDownColor: "#fb7185" });
  ema10 = chart.addLineSeries({ color: "#60a5fa", lineWidth: 2 });
  ema20 = chart.addLineSeries({ color: "#fbbf24", lineWidth: 2 });
  ema50 = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1 });
  ema200 = chart.addLineSeries({ color: "#94a3b8", lineWidth: 1 });
}

async function loadSymbol(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) return;
  const titleEl = $("chartTitle");
  const subEl = $("chartSubtitle");
  if (titleEl) titleEl.textContent = `${symbol} — Inspector`;
  if (subEl) subEl.textContent = "Loading chart...";

  let chartData, summary;
  try {
    chartData = await api(`/api/cockpit/${symbol}/chart`);
    summary = await api(`/api/cockpit/${symbol}/summary`);
  } catch (e) {
    if (subEl) subEl.textContent = `Load failed: ${e.message}`;
    return;
  }
  resetChart();
  if (!chartData.candles || chartData.candles.length === 0) {
    if (subEl) subEl.textContent = "No price history found.";
    return;
  }
  candleSeries.setData(chartData.candles);
  ema10.setData(chartData.ema10 || []);
  ema20.setData(chartData.ema20 || []);
  ema50.setData(chartData.ema50 || []);
  ema200.setData(chartData.ema200 || []);
  if (subEl) subEl.textContent = `${summary.sector || "Unknown sector"} · ₹${fmt(summary.mcap_cr)} cr · Fund ${fmt(summary.fund_score)}`;

  const setup = chartData.swing;
  const setupBadge = $("setupBadge");
  const setupSummary = $("setupSummary");

  if (setup) {
    if (setupBadge) { setupBadge.className = "badge good"; setupBadge.textContent = "Valid setup"; }
    candleSeries.createPriceLine({ price: setup.trigger, color: "#34d399", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: "Trigger" });
    candleSeries.createPriceLine({ price: setup.stop, color: "#fb7185", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: "PDL Stop" });
    candleSeries.createPriceLine({ price: setup.target, color: "#60a5fa", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "Target 3R" });
    if (setupSummary) {
      setupSummary.innerHTML = `
        <div class="level"><span>Trigger</span><strong>${setup.trigger}</strong></div>
        <div class="level"><span>PDL Stop</span><strong>${setup.stop}</strong></div>
        <div class="level"><span>Target (3R)</span><strong>${setup.target}</strong></div>
        <button class="toggle-btn" data-target="setupDetails">Show setup details</button>
        <div id="setupDetails" class="details-panel hidden">
          <div class="level"><span>Pullback</span><strong>${(setup.pullback * 100).toFixed(1)}%</strong></div>
          <div class="level"><span>Impulse</span><strong>${(setup.impulse * 100).toFixed(1)}%</strong></div>
          <div class="level"><span>EMA Zone</span><strong>${setup.zone}</strong></div>
          <div class="level"><span>Shape score</span><strong>${setup.shape ?? "—"}/100</strong></div>
        </div>`;
    }
    try {
      const sz = await api(`/api/sizing/${symbol}?trigger=${setup.trigger}&stop=${setup.stop}&shape=${setup.shape ?? ""}`);
      renderSizing(sz);
    } catch (e) {}
  } else {
    if (setupBadge) { setupBadge.className = "badge muted"; setupBadge.textContent = "No live setup"; }
    if (setupSummary) {
      setupSummary.innerHTML = `
        <div class="level"><span>Symbol</span><strong>${symbol}</strong></div>
        <div class="level"><span>Status</span><strong>${summary.status || "—"}</strong></div>
        <div class="level"><span>Fund Score</span><strong>${fmt(summary.fund_score)}</strong></div>
        <div class="level"><span>Mcap</span><strong>₹${fmt(summary.mcap_cr)} cr</strong></div>`;
    }
    try {
      const sz = await api(`/api/sizing/${symbol}`);
      renderSizing(sz);
    } catch (e) {}
  }

  // Machine P(WIN) with progressive disclosure
  try {
    const meta = await api(`/api/meta/${symbol}`);
    if (meta && meta.p_win != null && setupSummary) {
      const why = (meta.why || []).map(w => `<div class="level"><span>why · ${w.feature}</span><strong>${w.impact > 0 ? "+" : ""}${w.impact}</strong></div>`).join("");
      const whyBlock = why
        ? `<button class="toggle-btn" data-target="shapDetails">Show feature contributions</button>
           <div id="shapDetails" class="details-panel hidden">
             <div class="level"><span>P(WIN)</span><strong>${(meta.p_win * 100).toFixed(0)}%</strong></div>
             ${why}
           </div>`
        : `<div class="level"><span>P(WIN)</span><strong>${(meta.p_win * 100).toFixed(0)}%</strong></div>`;
      setupSummary.innerHTML += whyBlock;
    }
  } catch (e) {}

  loadDelivery(symbol);

  const newsBox = $("newsList");
  if (newsBox) {
    newsBox.innerHTML = "";
    if (summary.news && summary.news.length) {
      summary.news.forEach(n => {
        const div = document.createElement("div");
        div.className = "news-item";
        div.textContent = `[${n.age_days}d] ${n.label || "neutral"} — ${n.title}`;
        newsBox.appendChild(div);
      });
    } else {
      newsBox.textContent = "No stored news.";
    }
  }
  if (chart) chart.timeScale().fitContent();
}

// ============================================================
// Sizing — progressive disclosure
// ============================================================
function renderSizing(sz) {
  let box = $("sizingBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "sizingBox";
    box.className = "setup-box";
    box.style.marginTop = "14px";
    const panel = $("setupSummary") ? $("setupSummary").parentElement : null;
    if (panel) panel.appendChild(box);
  }

  // Build the compact answer first
  let compact, details;
  if (sz.error) {
    compact = `<div class="level"><span>Sizing</span><strong>unavailable yet</strong></div>`;
    details = capitalEditor(sz.capital);
  } else if (sz.shares !== undefined) {
    compact = `<div class="level"><span>Suggested position</span><strong>₹${sz.suggested_value.toLocaleString()} (${sz.alloc_pct}%)</strong></div>
      <div class="level"><span>Qty @ trigger</span><strong>${sz.shares} shares</strong></div>`;
    details = `
      <div class="level"><span>Capital</span><strong>₹${sz.capital.toLocaleString()}</strong></div>
      <div class="level"><span>Win prob (${sz.basis})</span><strong>${(sz.p_win * 100).toFixed(0)}%</strong></div>
      <div class="level"><span>Regime (${sz.regime_level})</span><strong>×${sz.regime_mult}</strong></div>
      <div class="level"><span>Quality (shape ${sz.shape_score ?? "—"})</span><strong>×${sz.quality_mult}</strong></div>
      <div class="level"><span>Kelly / Half-Kelly</span><strong>${sz.kelly_pct}% / ${sz.half_kelly_pct}%</strong></div>
      <div class="level"><span>Binding cap</span><strong>${sz.binding_cap}</strong></div>
      <div class="level"><span>Max loss at stop</span><strong>₹${sz.risk_amount.toLocaleString()} (${sz.risk_pct}%)</strong></div>`;
  } else {
    compact = `<div class="level"><span>Suggested allocation</span><strong>${sz.alloc_pct}% of capital</strong></div>`;
    details = `
      <div class="level"><span>Capital</span><strong>₹${sz.capital.toLocaleString()}</strong></div>
      <div class="level"><span>Win prob (${sz.basis})</span><strong>${(sz.p_win * 100).toFixed(0)}%</strong></div>
      <div class="level"><span>Regime (${sz.regime_level})</span><strong>×${sz.regime_mult}</strong></div>
      <div class="level"><span>Quality (shape ${sz.shape_score ?? "—"})</span><strong>×${sz.quality_mult}</strong></div>`;
  }

  const html = `
    <h3 style="margin:0;font-size:15px;">💰 Position Sizing</h3>
    ${compact}
    <button class="toggle-btn" data-target="sizingDetails">Show derivation</button>
    <div id="sizingDetails" class="details-panel hidden">
      ${details}
      ${capitalEditor(sz.capital)}
    </div>`;
  box.innerHTML = html;
  bindCapitalSave();
}

function capitalEditor(cap) {
  return `<div class="level"><span>Set capital</span><strong style="display:flex;gap:6px;">
    <input id="capitalInput" style="min-width:110px;padding:6px 8px;" type="number" value="${cap || 1000000}"/>
    <button id="saveCapitalBtn" style="padding:6px 10px;">Save</button>
  </strong></div>`;
}

function bindCapitalSave() {
  const btn = $("saveCapitalBtn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const v = parseFloat($("capitalInput").value);
    if (!v || v <= 0) { alert("Enter a valid capital amount"); return; }
    try {
      await api("/api/sizing/capital", { method: "POST", body: JSON.stringify({ capital: v }) });
      const titleEl = $("chartTitle");
      const sym = (titleEl ? titleEl.textContent : "").split(" ")[0];
      if (sym) loadSymbol(sym);
    } catch (e) { alert("Save failed: " + e.message); }
  });
}

// ============================================================
// Delivery — progressive disclosure
// ============================================================
async function loadDelivery(symbol) {
  const panel = $("setupSummary") ? $("setupSummary").parentElement : null;
  if (!panel) return;
  let box = $("deliveryBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "deliveryBox";
    box.className = "setup-box";
    box.style.marginTop = "14px";
    panel.appendChild(box);
  }
  try {
    const dv = await api(`/api/delivery/${symbol}`);
    const hist = dv.history || [];
    const last = hist[0];
    if (last || dv.score != null) {
      box.innerHTML = `
        <h3 style="margin:0;font-size:15px;">📦 Delivery %</h3>
        <div class="level"><span>Conviction score</span><strong>${dv.score != null ? (dv.score * 100).toFixed(0) + "/100" : "—"}</strong></div>
        <button class="toggle-btn" data-target="deliveryDetails">Show raw delivery data</button>
        <div id="deliveryDetails" class="details-panel hidden">
          <div class="level"><span>Latest (${last ? last.date : "—"})</span><strong>${last ? last.delivery_pct + "%" : "—"}</strong></div>
          <div class="level"><span>Traded / Deliverable</span><strong>${last ? (last.traded_qty / 100000).toFixed(1) + "L / " + (last.deliverable_qty / 100000).toFixed(1) + "L" : "—"}</strong></div>
        </div>`;
    } else {
      box.innerHTML = `<h3 style="margin:0;font-size:15px;">📦 Delivery %</h3>
        <div class="level"><span>Status</span><strong>no data yet</strong></div>`;
    }
  } catch (e) {
    box.innerHTML = `<h3 style="margin:0;font-size:15px;">📦 Delivery %</h3>
      <div class="level"><span>Status</span><strong>endpoint unavailable</strong></div>`;
  }
}

// ============================================================
// Screener (still on Research tab sidebar)
// ============================================================
async function loadScreener(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) { alert("Enter a symbol in the search box first."); return; }
  const badge = $("screenerBadge"), checksBox = $("screenerChecks"), metricsBox = $("screenerMetrics");
  if (!badge) return;
  badge.className = "badge muted"; badge.textContent = "Scanning...";
  try {
    const r = await api(`/api/screener/${symbol}`);
    if (r.error) { badge.textContent = "Error"; checksBox.innerHTML = `<p>${r.error}</p>`; return; }
    const ok = !!r.overall_signal;
    badge.className = ok ? "badge good" : "badge muted"; badge.textContent = ok ? "✅ LIVE SIGNAL" : "No signal";
    metricsBox.innerHTML = `
      <div class="level"><span>Symbol</span><strong>${r.ticker}</strong></div>
      <div class="level"><span>Price</span><strong>₹${r.current_price}</strong></div>
      <div class="level"><span>EMA200</span><strong>${r.ema_200}</strong></div>
      <div class="level"><span>Momentum 1M / 3M</span><strong>${r.momentum_1m} / ${r.momentum_3m}</strong></div>
      <div class="level"><span>vs 52W High</span><strong>${r.proximity_52w}</strong></div>
      <div class="level"><span>Impulse Gain</span><strong>${r.impulse_gain}</strong></div>
      <div class="level"><span>Pullback Depth</span><strong>${r.pullback_depth}</strong></div>
      <div class="level"><span>Days Since High</span><strong>${r.days_since_high}</strong></div>
      <div class="level"><span>3-Day Tightness</span><strong>${r.tightness_pct}</strong></div>`;
    checksBox.innerHTML = Object.entries(r.checks || {}).map(([k, v]) => `<div class="level"><span>${v ? "✅" : "❌"} ${k}</span><strong>${v ? "PASS" : "FAIL"}</strong></div>`).join("");
  } catch (e) { badge.textContent = "API error"; checksBox.innerHTML = `<p>${e.message}</p>`; }
}

async function runSwingScan() {
  const btn = $("runSwingBtn");
  if (btn) btn.textContent = "Running...";
  try {
    await api("/api/swing/scan", { method: "POST" });
    setTimeout(async () => {
      await loadSwing();
      if (btn) btn.textContent = "Run Swing Scan";
    }, 4000);
  } catch (e) {
    if (btn) btn.textContent = "Run Swing Scan";
    alert("Swing scan failed: " + e.message);
  }
}

// ============================================================
// Init
// ============================================================
async function refreshAll() {
  await Promise.all([
    loadHealth(), loadRegime(), loadTopPicks(), loadSwing(),
    loadPatterns(), loadRadar(),
  ]);
}

document.addEventListener("DOMContentLoaded", () => {
  const rb = $("refreshBtn");
  if (rb) rb.addEventListener("click", refreshAll);
  const lsb = $("loadSymbolBtn");
  if (lsb) lsb.addEventListener("click", () => {
    setView("research");
    loadSymbol($("symbolSearch").value);
  });
  const ss = $("symbolSearch");
  if (ss) ss.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { setView("research"); loadSymbol(ss.value); }
  });
  const rsb = $("runSwingBtn");
  if (rsb) rsb.addEventListener("click", runSwingScan);
  const rsc = $("runScreenerBtn");
  if (rsc) rsc.addEventListener("click", () => {
    setView("research");
    loadScreener($("symbolSearch").value);
  });
  const rps = $("runPatternScan");
  if (rps) rps.addEventListener("click", runPatternScan);
  const rrb = $("runResearchBtn");
  if (rrb) rrb.addEventListener("click", () => {
    const titleEl = $("chartTitle");
    const sym = (titleEl ? titleEl.textContent : "").split(" ")[0];
    if (sym && window.loadResearch) window.loadResearch(sym);
  });
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });
  refreshAll();
});