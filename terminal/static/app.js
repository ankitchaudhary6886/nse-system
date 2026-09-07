let chart = null, candleSeries = null, ema10 = null, ema20 = null, ema50 = null, ema200 = null;
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
}
function fmt(v, suffix = "") { return (v === null || v === undefined || Number.isNaN(v)) ? "—" : `${v}${suffix}`; }
function outcomeBadge(v) { return `<span class="outcome ${v || "PENDING"}">${v || "PENDING"}</span>`; }

function setView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active-view"));
  const el = $("view-" + name);
  if (el) el.classList.add("active-view");
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  const titles = { picks: "Top Picks", overview: "Overview", screener: "Screener", swing: "Swing Desk", ledger: "Ledger", radar: "Radar" };
  const t = $("viewTitle");
  if (t) t.textContent = titles[name] || "Top Picks";
  if (name === "overview" && chart) setTimeout(() => chart.timeScale().fitContent(), 50);
  if (name === "ledger") loadLedger();
}

async function loadHealth() { try { const h = await api("/api/health"); $("healthStatus").textContent = `${h.prices_rows.toLocaleString()} price rows`; } catch (e) { $("healthStatus").textContent = "Offline"; } }

async function loadRegime() {
  const box = $("regimeBanner");
  try {
    const r = await api("/api/regime");
    box.classList.remove("loading", "bull", "defensive");
    let regimeHtml = "";
    if (r.stance === "BULLISH") { box.classList.add("bull"); regimeHtml = `🟢 <strong>BULLISH / AGGRESSIVE</strong> — ${r.symbol} close ${r.index_close} > EMA10 ${r.ema10}. New long setups allowed.`; }
    else if (r.stance === "DEFENSIVE") { box.classList.add("defensive"); regimeHtml = `🛑 <strong>DEFENSIVE / CASH</strong> — ${r.symbol} close ${r.index_close} < EMA10 ${r.ema10}. No new long entries.`; }
    else { regimeHtml = `⚠️ Regime unavailable: ${r.error || ""}`; }
    let macroHtml = "";
    try { const m = await api("/api/macro"); if (m && m.fii_net !== null && m.dii_net !== null) { const net = m.fii_net + m.dii_net; const icon = net >= 0 ? "🟢" : "🛑"; macroHtml = `<div style="margin-top:8px; font-size:14px; opacity:0.9;">${icon} Smart Money Flow: FII ${m.fii_net > 0 ? "+" : ""}${m.fii_net.toFixed(0)}Cr / DII ${m.dii_net > 0 ? "+" : ""}${m.dii_net.toFixed(0)}Cr (Net: ${net > 0 ? "+" : ""}${net.toFixed(0)}Cr)</div>`; } } catch (e) {}
    box.innerHTML = regimeHtml + macroHtml;
  } catch (e) { box.classList.add("defensive"); box.innerHTML = "⚠️ Regime API unavailable."; }
}

function createPickCard(item, rank) {
  const div = document.createElement("div");
  div.className = "stock-card";
  div.innerHTML = `<strong>#${rank} ${item.symbol} ${item.setup ? '<span class="outcome WIN">🏄 LIVE SETUP</span>' : ""}</strong><span>Composite ${(item.composite * 100).toFixed(0)} · 🧠 P(WIN) ${(item.p_win * 100).toFixed(0)}% · 🏦 accum ${item.accum.toFixed(2)}</span><span>${item.sector || "Unknown sector"} · sector RS ${(item.sector_rs * 100).toFixed(0)}</span>`;
  div.addEventListener("click", () => { setView("overview"); loadSymbol(item.symbol); });
  return div;
}
async function loadTopPicks() { try { const data = await api("/api/toppicks"); const box = $("picksList"); box.innerHTML = ""; (data.picks || []).forEach((x, i) => box.appendChild(createPickCard(x, i + 1))); } catch (e) {} }

function trancheLadder(setup) {
  const R = setup.trigger - setup.stop;
  return `<div class="level"><span>Stage 1 · Initial SL (PDL)</span><strong>${setup.stop}</strong></div><div class="level"><span>Stage 2 · +2R → SL to BE</span><strong>${(setup.trigger + 2 * R).toFixed(2)}</strong></div><div class="level"><span>Stage 3 · +4R → exit 1/3</span><strong>${(setup.trigger + 4 * R).toFixed(2)}</strong></div><div class="level"><span>Stage 4 · trail 10 EMA</span><strong>after +4R</strong></div><div class="level"><span>Stage 5 · trail 20 EMA / climax</span><strong>runner</strong></div>`;
}

async function loadSwing() {
  const data = await api("/api/swing/signals");
  const tbody = $("swingTable"); tbody.innerHTML = "";
  const signals = data.signals || []; const score = data.scorecard || {};
  const ms = $("mSignals"); if (ms) ms.textContent = signals.length;
  const mw = $("mWinRate"); if (mw) mw.textContent = data.win_rate === null ? "—" : `${data.win_rate}%`;
  const mo = $("mOpen"); if (mo) mo.textContent = `${score.OPEN || 0} / ${score.PENDING || 0}`;
  for (const s of signals) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${s.date}</td><td><strong>${s.symbol}</strong> ${s.p_win != null ? `<span class="outcome PENDING">🧠${(s.p_win * 100).toFixed(0)}%</span>` : ""}</td><td>${fmt(s.trigger)}</td><td>${fmt(s.stop)}</td><td>${fmt(s.target)}</td><td>${fmt(s.risk_pct, "%")}</td><td>${s.pullback ? (s.pullback * 100).toFixed(1) + "%" : "—"}</td><td>${s.impulse ? (s.impulse * 100).toFixed(1) + "%" : "—"}</td><td>${s.ema_zone || "—"}</td><td>${outcomeBadge(s.outcome)}</td>`;
    tr.addEventListener("click", () => { setView("overview"); loadSymbol(s.symbol); });
    tbody.appendChild(tr);
  }
  if (signals.length > 0) loadSymbol(signals[0].symbol);
}

async function loadLedger() {
  try {
    const stats = await api("/api/ledger/stats");
    const trades = await api("/api/ledger/trades");
    const box = $("ledgerStats");
    if (!stats || stats.total_trades === 0) { box.innerHTML = "<p>No graded trades yet. Run swing scans daily to build history.</p>"; }
    else {
      box.innerHTML = `<div class="level"><span>Total Trades</span><strong>${stats.total_trades}</strong></div><div class="level"><span>Wins / Losses</span><strong>${stats.wins} / ${stats.losses}</strong></div><div class="level"><span>Win Rate</span><strong>${stats.win_rate}%</strong></div><div class="level"><span>Profit Factor</span><strong>${stats.profit_factor}</strong></div><div class="level"><span>Expectancy (R)</span><strong>${stats.expectancy_r} R</strong></div><div class="level"><span>Total Return</span><strong>${stats.total_r} R</strong></div><div class="level"><span>Max Drawdown</span><strong>${stats.max_drawdown_r} R</strong></div>`;
    }
    const tbody = $("ledgerTable"); tbody.innerHTML = "";
    (trades.trades || []).forEach(t => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${t.date}</td><td><strong>${t.symbol}</strong></td><td>${fmt(t.trigger)}</td><td>${fmt(t.stop)}</td><td>${fmt(t.target)}</td><td>${outcomeBadge(t.outcome)}</td>`;
      tr.addEventListener("click", () => { setView("overview"); loadSymbol(t.symbol); });
      tbody.appendChild(tr);
    });
  } catch (e) { $("ledgerStats").innerHTML = `<p>Error loading ledger: ${e.message}</p>`; }
}

function createRadarCard(item) {
  const div = document.createElement("div");
  div.className = "stock-card";
  div.innerHTML = `<strong>${item.symbol}</strong><span>1M ${fmt(item.perf1m, "%")} · 3M ${fmt(item.perf3m, "%")} · Vol ${fmt(item.relvol, "x")}</span><span>₹${fmt(item.mcap_cr)} cr mcap</span>${item.p_win != null ? `<span>🧠 P(WIN) ${(item.p_win * 100).toFixed(0)}%</span>` : ""}`;
  div.addEventListener("click", () => { setView("overview"); loadSymbol(item.symbol); });
  return div;
}
async function loadRadar() {
  const data = await api("/api/radar");
  const mu = $("mUniverse"); if (mu) mu.textContent = data.total || "—";
  const g = data.groups || {};
  const m = $("radarMomentum"), v = $("radarVolume"), t = $("radarTurn");
  if (m) m.innerHTML = ""; if (v) v.innerHTML = ""; if (t) t.innerHTML = "";
  (g["Momentum"] || []).slice(0, 18).forEach(x => m && m.appendChild(createRadarCard(x)));
  (g["Volume Spike"] || []).slice(0, 18).forEach(x => v && v.appendChild(createRadarCard(x)));
  (g["Turnaround"] || []).slice(0, 18).forEach(x => t && t.appendChild(createRadarCard(x)));
}

async function loadScreener(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) { alert("Enter a symbol in the search box first."); return; }
  const badge = $("screenerBadge"), checksBox = $("screenerChecks"), metricsBox = $("screenerMetrics");
  badge.className = "badge muted"; badge.textContent = "Scanning...";
  try {
    const r = await api(`/api/screener/${symbol}`);
    if (r.error) { badge.textContent = "Error"; checksBox.innerHTML = `<p>${r.error}</p>`; return; }
    const ok = !!r.overall_signal;
    badge.className = ok ? "badge good" : "badge muted"; badge.textContent = ok ? "✅ LIVE SIGNAL" : "No signal";
    metricsBox.innerHTML = `<div class="level"><span>Symbol</span><strong>${r.ticker}</strong></div><div class="level"><span>Price</span><strong>₹${r.current_price}</strong></div><div class="level"><span>EMA200</span><strong>${r.ema_200}</strong></div><div class="level"><span>Momentum 1M / 3M</span><strong>${r.momentum_1m} / ${r.momentum_3m}</strong></div><div class="level"><span>vs 52W High</span><strong>${r.proximity_52w}</strong></div><div class="level"><span>Impulse Gain</span><strong>${r.impulse_gain}</strong></div><div class="level"><span>Pullback Depth</span><strong>${r.pullback_depth}</strong></div><div class="level"><span>Days Since High</span><strong>${r.days_since_high}</strong></div><div class="level"><span>3-Day Tightness</span><strong>${r.tightness_pct}</strong></div>`;
    checksBox.innerHTML = Object.entries(r.checks || {}).map(([k, v]) => `<div class="level"><span>${v ? "✅" : "❌"} ${k}</span><strong>${v ? "PASS" : "FAIL"}</strong></div>`).join("");
  } catch (e) { badge.textContent = "API error"; checksBox.innerHTML = `<p>${e.message}</p>`; }
}

async function loadBandScan() {
  const btn = $("scanBandBtn"), box = $("bandHits");
  btn.textContent = "Scanning..."; box.innerHTML = "<p>Scanning smallcap band (DB-only)...</p>";
  try {
    const r = await api("/api/screener/scan?limit=60");
    const hits = r.hits || [];
    if (!hits.length) { box.innerHTML = "<p>No live baseline+VCP setups in the band right now (normal on most days).</p>"; }
    else {
      box.innerHTML = "";
      hits.forEach(h => {
        const div = document.createElement("div"); div.className = "stock-card";
        div.innerHTML = `<strong>${h.ticker} ✅ LIVE SIGNAL</strong><span>Price ₹${h.current_price} · EMA200 ${h.ema_200}</span><span>PB ${h.pullback_depth} · Tight ${h.tightness_pct} · ${h.days_since_high}d since high</span>`;
        div.addEventListener("click", () => loadScreener(h.ticker));
        box.appendChild(div);
      });
    }
  } catch (e) { box.innerHTML = `<p>Band scan failed: ${e.message}</p>`; }
  btn.textContent = "Scan Whole Band";
}

function resetChart() {
  const el = $("chart"); el.innerHTML = "";
  chart = LightweightCharts.createChart(el, { layout: { background: { color: "transparent" }, textColor: "#9fb0cc" }, grid: { vertLines: { color: "rgba(255,255,255,.05)" }, horzLines: { color: "rgba(255,255,255,.05)" } }, rightPriceScale: { borderColor: "rgba(255,255,255,.08)" }, timeScale: { borderColor: "rgba(255,255,255,.08)" }, crosshair: { mode: LightweightCharts.CrosshairMode.Normal } });
  candleSeries = chart.addCandlestickSeries({ upColor: "#34d399", downColor: "#fb7185", borderVisible: false, wickUpColor: "#34d399", wickDownColor: "#fb7185" });
  ema10 = chart.addLineSeries({ color: "#60a5fa", lineWidth: 2 });
  ema20 = chart.addLineSeries({ color: "#fbbf24", lineWidth: 2 });
  ema50 = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1 });
  ema200 = chart.addLineSeries({ color: "#94a3b8", lineWidth: 1 });
}

async function loadSymbol(symbol) {
  symbol = symbol.trim().toUpperCase(); if (!symbol) return;
  $("chartTitle").textContent = `${symbol} — Setup Inspector`; $("chartSubtitle").textContent = "Loading chart...";
  const chartData = await api(`/api/cockpit/${symbol}/chart`);
  const summary = await api(`/api/cockpit/${symbol}/summary`);
  resetChart();
  if (!chartData.candles || chartData.candles.length === 0) { $("chartSubtitle").textContent = "No price history found."; return; }
  candleSeries.setData(chartData.candles); ema10.setData(chartData.ema10 || []); ema20.setData(chartData.ema20 || []); ema50.setData(chartData.ema50 || []); ema200.setData(chartData.ema200 || []);
  $("chartSubtitle").textContent = `${summary.sector || "Unknown sector"} · ₹${fmt(summary.mcap_cr)} cr · Fund ${fmt(summary.fund_score)}`;
  const setup = chartData.swing;
  if (setup) {
    $("setupBadge").className = "badge good"; $("setupBadge").textContent = "Valid setup";
    candleSeries.createPriceLine({ price: setup.trigger, color: "#34d399", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: "Trigger" });
    candleSeries.createPriceLine({ price: setup.stop, color: "#fb7185", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: "PDL Stop" });
    candleSeries.createPriceLine({ price: setup.target, color: "#60a5fa", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "Target" });
    $("setupSummary").innerHTML = `<div class="level"><span>Trigger</span><strong>${setup.trigger}</strong></div><div class="level"><span>PDL Stop</span><strong>${setup.stop}</strong></div><div class="level"><span>Target (2R)</span><strong>${setup.target}</strong></div><div class="level"><span>Pullback</span><strong>${(setup.pullback * 100).toFixed(1)}%</strong></div><div class="level"><span>Impulse</span><strong>${(setup.impulse * 100).toFixed(1)}%</strong></div><div class="level"><span>EMA Zone</span><strong>${setup.zone}</strong></div><div class="level"><span>Shape score</span><strong>${setup.shape ?? "—"}/100</strong></div>${trancheLadder(setup)}`;
  } else {
    $("setupBadge").className = "badge muted"; $("setupBadge").textContent = "No live setup";
    $("setupSummary").innerHTML = `<div class="level"><span>Symbol</span><strong>${symbol}</strong></div><div class="level"><span>Status</span><strong>${summary.status || "—"}</strong></div><div class="level"><span>Fund Score</span><strong>${fmt(summary.fund_score)}</strong></div><div class="level"><span>Mcap</span><strong>₹${fmt(summary.mcap_cr)} cr</strong></div>`;
  }
  try {
    const meta = await api(`/api/meta/${symbol}`);
    if (meta && meta.p_win != null) {
      const why = (meta.why || []).map(w => `<div class="level"><span>why · ${w.feature}</span><strong>${w.impact > 0 ? "+" : ""}${w.impact}</strong></div>`).join("");
      $("setupSummary").innerHTML += `<div class="level"><span>🧠 Machine P(WIN)</span><strong>${(meta.p_win * 100).toFixed(0)}%</strong></div>` + why;
    }
  } catch (e) {}
  const newsBox = $("newsList"); newsBox.innerHTML = "";
  if (summary.news && summary.news.length) { summary.news.forEach(n => { const div = document.createElement("div"); div.className = "news-item"; div.textContent = `[${n.age_days}d] ${n.label || "neutral"} — ${n.title}`; newsBox.appendChild(div); }); }
  else { newsBox.textContent = "No stored news."; }
  chart.timeScale().fitContent();
}

async function runSwingScan() {
  $("runSwingBtn").textContent = "Running...";
  try { await api("/api/swing/scan", { method: "POST" }); setTimeout(async () => { await loadSwing(); $("runSwingBtn").textContent = "Run Swing Scan"; }, 4000); }
  catch (e) { $("runSwingBtn").textContent = "Run Swing Scan"; alert("Swing scan failed: " + e.message); }
}

async function refreshAll() { await Promise.all([loadHealth(), loadRegime(), loadTopPicks(), loadSwing(), loadRadar()]); }

document.addEventListener("DOMContentLoaded", () => {
  $("refreshBtn").addEventListener("click", refreshAll);
  $("loadSymbolBtn").addEventListener("click", () => { setView("overview"); loadSymbol($("symbolSearch").value); });
  $("symbolSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") { setView("overview"); loadSymbol($("symbolSearch").value); } });
  $("runSwingBtn").addEventListener("click", runSwingScan);
  $("runScreenerBtn").addEventListener("click", () => { setView("screener"); loadScreener($("symbolSearch").value); });
  $("scanBandBtn").addEventListener("click", loadBandScan);
  document.querySelectorAll(".nav-btn").forEach(btn => { btn.addEventListener("click", () => setView(btn.dataset.view)); });
  refreshAll();
});