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
  const titles = { picks: "Top Picks", overview: "Overview", screener: "Screener", swing: "Swing Desk", patterns: "Patterns", ledger: "Ledger", radar: "Radar" };
  const t = $("viewTitle");
  if (t) t.textContent = titles[name] || "Top Picks";
  if (name === "overview" && chart) setTimeout(() => chart.timeScale().fitContent(), 50);
  if (name === "ledger") loadLedger();
  if (name === "patterns") loadPatterns();
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
    try { const gs = await api("/api/patterns/stats"); gate = gs.stats || {}; } catch (e) { gate = {}; }
    const vals = Object.values(gate);
    const en = vals.filter(v => v.status === "ENABLED").length;
    const pr = vals.filter(v => v.status === "PROVISIONAL").length;
    const di = vals.filter(v => v.status === "DISABLED").length;
    if (st) st.innerHTML = `<span>Stored formations</span><strong>${rows.length}${rows.length ? " · latest " + rows[0].date : ""} · gate: ${en} ON / ${pr} PROV / ${di} OFF</strong>`;
    list.innerHTML = "";
    if (!rows.length) {
      list.innerHTML = "<p>No stored patterns yet. Press Run Full Scan above (or wait for the 18:05 IST nightly job), then Refresh.</p>";
      return;
    }
    rows.forEach(p => {
      const div = document.createElement("div");
      div.className = "stock-card";
      const sauce = sauceLine(p);
      div.innerHTML = `<strong>${p.symbol} · ${(p.pattern || "").replace(/_/g, " ")}</strong>
        <span>${dirBadge(p.direction)} ${statusBadge(p.status)} ${gateBadge(gate[p.pattern])}</span>
        <span>Breakout ₹${p.breakout_level ?? "—"} · Stop ₹${p.stop_level ?? "—"} · Target ₹${p.target_level ?? "—"}</span>
        ${sauce ? `<span>${sauce}</span>` : ""}
        <span>${p.notes || ""}</span>`;
      div.addEventListener("click", () => { setView("overview"); loadSymbol(p.symbol); });
      list.appendChild(div);
    });
  } catch (e) {
    if (st) st.innerHTML = `<span>Status</span><strong>pattern endpoint unavailable</strong>`;
    list.innerHTML = `<p>Pattern endpoint error: ${e.message}</p>`;
  }
}

async function runPatternScan() {
  const btn = $("runPatternScan");
  const st = $("patternStatus");
  btn.textContent = "Scan queued…";
  try {
    await api("/api/patterns/scan", { method: "POST" });
    if (st) st.innerHTML = `<span>Status</span><strong>scan running in background (a few minutes) — click Refresh afterwards</strong>`;
    setTimeout(loadPatterns, 60000);
  } catch (e) {
    if (st) st.innerHTML = `<span>Status</span><strong>scan start failed: ${e.message}</strong>`;
  }
  btn.textContent = "Run Full Scan";
}

async function loadValidation() {
  const statsBox = $("ledgerStats");
  if (!statsBox) return;
  let box = $("validationBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "validationBox";
    box.className = "setup-box";
    box.style.marginTop = "14px";
    statsBox.parentElement.appendChild(box);
  }
  try {
    const v = await api("/api/validate/latest");
    let html = `<h3 style="margin:0;font-size:15px;">🔬 Validation — is the edge real?</h3>`;
    const mc = v.mc, wf = v.wf;
    if (!mc && !wf) {
      html += `<div class="level"><span>Status</span><strong>no validation runs yet</strong></div><div class="level"><span>To seed</span><strong>VM: python validate.py all</strong></div>`;
    }
    if (mc) {
      if (mc.error) {
        html += `<div class="level"><span>Monte-Carlo</span><strong>${mc.error}</strong></div>`;
      } else {
        html += `<div class="level"><span>MC (${mc.run_date})</span><strong>${mc.n_trades} trades · ${mc.n_sim} sims</strong></div>
          <div class="level"><span>Win rate p5 / p50 / p95</span><strong>${(mc.win_rate.p5 * 100).toFixed(0)}% / ${(mc.win_rate.p50 * 100).toFixed(0)}% / ${(mc.win_rate.p95 * 100).toFixed(0)}%</strong></div>
          <div class="level"><span>Expectancy (p50)</span><strong>${mc.expectancy_r.p50} R per trade</strong></div>
          <div class="level"><span>Total R (p5 .. p95)</span><strong>${mc.total_r.p5} .. ${mc.total_r.p95}</strong></div>
          <div class="level"><span>Max drawdown (p95)</span><strong>${mc.max_dd_r.p95} R</strong></div>
          <div class="level"><span>P(negative total)</span><strong>${(mc.p_negative_total * 100).toFixed(0)}%</strong></div>`;
      }
    }
    if (wf && wf.verdict) {
      html += `<div class="level"><span>WF (${wf.run_date})</span><strong>${wf.verdict}</strong></div>
        <div class="level"><span>In-sample WR</span><strong>${wf.in_sample.win_rate == null ? "—" : (wf.in_sample.win_rate * 100).toFixed(0) + "%"} (${wf.in_sample.wins}W/${wf.in_sample.losses}L)</strong></div>
        <div class="level"><span>Out-of-sample WR</span><strong>${wf.out_sample.win_rate == null ? "—" : (wf.out_sample.win_rate * 100).toFixed(0) + "%"} (${wf.out_sample.wins}W/${wf.out_sample.losses}L)</strong></div>`;
    }
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<h3 style="margin:0;font-size:15px;">🔬 Validation</h3><div class="level"><span>Status</span><strong>endpoint unavailable (deploy validate batch)</strong></div>`;
  }
}

async function loadModelRuns() {
  const statsBox = $("ledgerStats");
  if (!statsBox) return;
  let box = $("modelRunsBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "modelRunsBox";
    box.className = "setup-box";
    box.style.marginTop = "14px";
    statsBox.parentElement.appendChild(box);
  }
  try {
    const data = await api("/api/model/runs?n=8");
    const runs = data.runs || [];
    let html = `<h3 style="margin:0;font-size:15px;">🧠 Model Runs — AUC history + C3 lift</h3>`;
    if (!runs.length) {
      html += `<div class="level"><span>Status</span><strong>no runs recorded yet</strong></div>
        <div class="level"><span>To seed</span><strong>VM: python model_report.py lift</strong></div>`;
      box.innerHTML = html;
      return;
    }
    const lift = runs.find(r => r.note === "c3_lift");
    const train = runs.find(r => r.note !== "c3_lift") || runs[0];
    html += `<div class="level"><span>Last retrain (${train.run_date})</span><strong>AUC ${train.auc == null ? "—" : train.auc} · top10 ${train.top10_win == null ? "—" : (train.top10_win * 100).toFixed(0) + "%"}</strong></div>
      <div class="level"><span>Rows / base win</span><strong>${train.rows || "—"} / ${train.base_win == null ? "—" : (train.base_win * 100).toFixed(1) + "%"}</strong></div>`;
    if (lift && lift.price_only_auc != null) {
      const d = lift.delta_auc;
      const verdict = d > 0.005 ? "context features ADD value" : (d < -0.005 ? "context features HURT — review C3" : "context features neutral");
      html += `<div class="level"><span>C3 lift (${lift.run_date})</span><strong>${verdict}</strong></div>
        <div class="level"><span>Full vs price-only AUC</span><strong>${lift.auc} vs ${lift.price_only_auc} (Δ ${d > 0 ? "+" : ""}${d})</strong></div>
        <div class="level"><span>Top10 Δ</span><strong>${lift.delta_top10 > 0 ? "+" : ""}${lift.delta_top10}</strong></div>`;
    } else {
      html += `<div class="level"><span>C3 lift</span><strong>not run yet — VM: python model_report.py lift</strong></div>`;
    }
    html += `<div class="level"><span>History (last 5)</span><strong>${runs.slice(0, 5).map(r => `${r.run_date.slice(5)}:${r.auc ?? "-"}`).join(" · ")}</strong></div>`;
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<h3 style="margin:0;font-size:15px;">🧠 Model Runs</h3><div class="level"><span>Status</span><strong>endpoint unavailable (deploy terminal_api v7+)</strong></div>`;
  }
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
    loadValidation();
    loadModelRuns();
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

function capitalEditor(cap) {
  return `<div class="level"><span>Set capital</span><strong style="display:flex;gap:6px;"><input id="capitalInput" style="min-width:110px;padding:6px 8px;" type="number" value="${cap || 1000000}"/><button id="saveCapitalBtn" style="padding:6px 10px;">Save</button></strong></div>`;
}

function renderSizing(sz) {
  let box = $("sizingBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "sizingBox";
    box.className = "setup-box";
    box.style.marginTop = "14px";
    const panel = $("setupSummary").parentElement;
    panel.appendChild(box);
  }
  let html = `<h3 style="margin:0;font-size:15px;">💰 Position Sizing (half-Kelly)</h3>`;
  if (sz.error) {
    html += `<div class="level"><span>Capital</span><strong>₹${(sz.capital || 0).toLocaleString()}</strong></div><div class="level"><span>Sizing</span><strong>unavailable yet</strong></div>` + capitalEditor(sz.capital);
    box.innerHTML = html;
    bindCapitalSave();
    return;
  }
  html += `<div class="level"><span>Capital</span><strong>₹${sz.capital.toLocaleString()}</strong></div>
    <div class="level"><span>Win prob (${sz.basis})</span><strong>${(sz.p_win * 100).toFixed(0)}%</strong></div>
    <div class="level"><span>Kelly / Half-Kelly</span><strong>${sz.kelly_pct}% / ${sz.half_kelly_pct}%</strong></div>
    <div class="level"><span>Alloc cap applied</span><strong>${sz.alloc_pct}%</strong></div>`;
  if (sz.shares !== undefined) {
    html += `<div class="level"><span>Suggested position</span><strong>₹${sz.suggested_value.toLocaleString()}</strong></div>
      <div class="level"><span>Qty @ trigger</span><strong>${sz.shares} shares</strong></div>
      <div class="level"><span>Max loss at stop</span><strong>₹${sz.risk_amount.toLocaleString()} (${sz.risk_pct}%)</strong></div>
      <div class="level"><span>Binding cap</span><strong>${sz.binding_cap}</strong></div>`;
  }
  html += capitalEditor(sz.capital);
  box.innerHTML = html;
  bindCapitalSave();
}

function bindCapitalSave() {
  const btn = $("saveCapitalBtn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const v = parseFloat($("capitalInput").value);
    if (!v || v <= 0) { alert("Enter a valid capital amount"); return; }
    try {
      await api("/api/sizing/capital", { method: "POST", body: JSON.stringify({ capital: v }) });
      const sym = $("chartTitle").textContent.split(" ")[0];
      if (sym) loadSymbol(sym);
    } catch (e) { alert("Save failed: " + e.message); }
  });
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
    try {
      const sz = await api(`/api/sizing/${symbol}?trigger=${setup.trigger}&stop=${setup.stop}`);
      renderSizing(sz);
    } catch (e) { /* sizing optional */ }
  } else {
    $("setupBadge").className = "badge muted"; $("setupBadge").textContent = "No live setup";
    $("setupSummary").innerHTML = `<div class="level"><span>Symbol</span><strong>${symbol}</strong></div><div class="level"><span>Status</span><strong>${summary.status || "—"}</strong></div><div class="level"><span>Fund Score</span><strong>${fmt(summary.fund_score)}</strong></div><div class="level"><span>Mcap</span><strong>₹${fmt(summary.mcap_cr)} cr</strong></div>`;
    try {
      const sz = await api(`/api/sizing/${symbol}`);
      renderSizing(sz);
    } catch (e) { /* sizing optional */ }
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

async function refreshAll() { await Promise.all([loadHealth(), loadRegime(), loadTopPicks(), loadSwing(), loadRadar(), loadPatterns()]); }

document.addEventListener("DOMContentLoaded", () => {
  $("refreshBtn").addEventListener("click", refreshAll);
  $("loadSymbolBtn").addEventListener("click", () => { setView("overview"); loadSymbol($("symbolSearch").value); });
  $("symbolSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") { setView("overview"); loadSymbol($("symbolSearch").value); } });
  $("runSwingBtn").addEventListener("click", runSwingScan);
  $("runScreenerBtn").addEventListener("click", () => { setView("screener"); loadScreener($("symbolSearch").value); });
  $("scanBandBtn").addEventListener("click", loadBandScan);
  $("runPatternScan").addEventListener("click", runPatternScan);
  document.querySelectorAll(".nav-btn").forEach(btn => { btn.addEventListener("click", () => setView(btn.dataset.view)); });
  refreshAll();
});