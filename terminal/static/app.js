let chart = null;
let candleSeries = null;
let ema10 = null;
let ema20 = null;
let ema50 = null;
let ema200 = null;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }

  return await res.json();
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v}${suffix}`;
}

function outcomeBadge(v) {
  return `<span class="outcome ${v || "PENDING"}">${v || "PENDING"}</span>`;
}

async function loadHealth() {
  try {
    const h = await api("/api/health");
    $("healthStatus").textContent = `${h.prices_rows.toLocaleString()} price rows`;
  } catch (e) {
    $("healthStatus").textContent = "Offline";
  }
}

async function loadRegime() {
  const box = $("regimeBanner");

  try {
    const r = await api("/api/regime");

    box.classList.remove("loading", "bull", "defensive");

    if (r.stance === "BULLISH") {
      box.classList.add("bull");
      box.innerHTML =
        `🟢 <strong>BULLISH / AGGRESSIVE</strong> — ${r.symbol} ` +
        `close ${r.index_close} > EMA10 ${r.ema10}. New long setups allowed.`;
    } else if (r.stance === "DEFENSIVE") {
      box.classList.add("defensive");
      box.innerHTML =
        `🛑 <strong>DEFENSIVE / CASH</strong> — ${r.symbol} ` +
        `close ${r.index_close} < EMA10 ${r.ema10}. No new long entries.`;
    } else {
      box.innerHTML = `⚠️ Regime unavailable: ${r.error || ""}`;
    }
  } catch (e) {
    box.classList.add("defensive");
    box.innerHTML = "⚠️ Regime API unavailable.";
  }
}

async function loadSwing() {
  const data = await api("/api/swing/signals");
  const tbody = $("swingTable");
  tbody.innerHTML = "";

  const signals = data.signals || [];
  const score = data.scorecard || {};

  $("mSignals").textContent = signals.length;
  $("mWinRate").textContent = data.win_rate === null ? "—" : `${data.win_rate}%`;
  $("mOpen").textContent =
    `${score.OPEN || 0} / ${score.PENDING || 0}`;

  for (const s of signals) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.date}</td>
      <td><strong>${s.symbol}</strong></td>
      <td>${fmt(s.trigger)}</td>
      <td>${fmt(s.stop)}</td>
      <td>${fmt(s.target)}</td>
      <td>${fmt(s.risk_pct, "%")}</td>
      <td>${s.pullback ? (s.pullback * 100).toFixed(1) + "%" : "—"}</td>
      <td>${s.impulse ? (s.impulse * 100).toFixed(1) + "%" : "—"}</td>
      <td>${s.ema_zone || "—"}</td>
      <td>${outcomeBadge(s.outcome)}</td>
    `;

    tr.addEventListener("click", () => {
      loadSymbol(s.symbol);
    });

    tbody.appendChild(tr);
  }

  if (signals.length > 0) {
    loadSymbol(signals[0].symbol);
  }
}

function createRadarCard(item) {
  const div = document.createElement("div");
  div.className = "stock-card";
  div.innerHTML = `
    <strong>${item.symbol}</strong>
    <span>1M ${fmt(item.perf1m, "%")} · 3M ${fmt(item.perf3m, "%")} · Vol ${fmt(item.relvol, "x")}</span>
    <span>₹${fmt(item.mcap_cr)} cr mcap</span>
  `;
  div.addEventListener("click", () => loadSymbol(item.symbol));
  return div;
}

async function loadRadar() {
  const data = await api("/api/radar");
  $("mUniverse").textContent = data.total || "—";

  const groups = data.groups || {};

  const m = $("radarMomentum");
  const v = $("radarVolume");
  const t = $("radarTurn");

  m.innerHTML = "";
  v.innerHTML = "";
  t.innerHTML = "";

  (groups["Momentum"] || []).slice(0, 18).forEach(x => m.appendChild(createRadarCard(x)));
  (groups["Volume Spike"] || []).slice(0, 18).forEach(x => v.appendChild(createRadarCard(x)));
  (groups["Turnaround"] || []).slice(0, 18).forEach(x => t.appendChild(createRadarCard(x)));
}

function resetChart() {
  const el = $("chart");
  el.innerHTML = "";

  chart = LightweightCharts.createChart(el, {
    layout: {
      background: { color: "transparent" },
      textColor: "#9fb0cc",
    },
    grid: {
      vertLines: { color: "rgba(255,255,255,.05)" },
      horzLines: { color: "rgba(255,255,255,.05)" },
    },
    rightPriceScale: {
      borderColor: "rgba(255,255,255,.08)",
    },
    timeScale: {
      borderColor: "rgba(255,255,255,.08)",
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
  });

  candleSeries = chart.addCandlestickSeries({
    upColor: "#34d399",
    downColor: "#fb7185",
    borderVisible: false,
    wickUpColor: "#34d399",
    wickDownColor: "#fb7185",
  });

  ema10 = chart.addLineSeries({ color: "#60a5fa", lineWidth: 2 });
  ema20 = chart.addLineSeries({ color: "#fbbf24", lineWidth: 2 });
  ema50 = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1 });
  ema200 = chart.addLineSeries({ color: "#94a3b8", lineWidth: 1 });
}

async function loadSymbol(symbol) {
  symbol = symbol.trim().toUpperCase();
  if (!symbol) return;

  $("chartTitle").textContent = `${symbol} — Setup Inspector`;
  $("chartSubtitle").textContent = "Loading chart...";

  const chartData = await api(`/api/cockpit/${symbol}/chart`);
  const summary = await api(`/api/cockpit/${symbol}/summary`);

  resetChart();

  if (!chartData.candles || chartData.candles.length === 0) {
    $("chartSubtitle").textContent = "No price history found.";
    return;
  }

  candleSeries.setData(chartData.candles);
  ema10.setData(chartData.ema10 || []);
  ema20.setData(chartData.ema20 || []);
  ema50.setData(chartData.ema50 || []);
  ema200.setData(chartData.ema200 || []);

  $("chartSubtitle").textContent =
    `${summary.sector || "Unknown sector"} · ` +
    `₹${fmt(summary.mcap_cr)} cr · Fund ${fmt(summary.fund_score)}`;

  const setup = chartData.swing;

  if (setup) {
    $("setupBadge").className = "badge good";
    $("setupBadge").textContent = "Valid setup";

    candleSeries.createPriceLine({
      price: setup.trigger,
      color: "#34d399",
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: true,
      title: "Trigger",
    });

    candleSeries.createPriceLine({
      price: setup.stop,
      color: "#fb7185",
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: true,
      title: "PDL Stop",
    });

    candleSeries.createPriceLine({
      price: setup.target,
      color: "#60a5fa",
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      title: "Target",
    });

    $("setupSummary").innerHTML = `
      <div class="level"><span>Trigger</span><strong>${setup.trigger}</strong></div>
      <div class="level"><span>PDL Stop</span><strong>${setup.stop}</strong></div>
      <div class="level"><span>Target</span><strong>${setup.target}</strong></div>
      <div class="level"><span>Pullback</span><strong>${(setup.pullback * 100).toFixed(1)}%</strong></div>
      <div class="level"><span>Impulse</span><strong>${(setup.impulse * 100).toFixed(1)}%</strong></div>
      <div class="level"><span>EMA Zone</span><strong>${setup.zone}</strong></div>
    `;
  } else {
    $("setupBadge").className = "badge muted";
    $("setupBadge").textContent = "No live setup";

    $("setupSummary").innerHTML = `
      <div class="level"><span>Symbol</span><strong>${symbol}</strong></div>
      <div class="level"><span>Status</span><strong>${summary.status || "—"}</strong></div>
      <div class="level"><span>Fund Score</span><strong>${fmt(summary.fund_score)}</strong></div>
      <div class="level"><span>Mcap</span><strong>₹${fmt(summary.mcap_cr)} cr</strong></div>
    `;
  }

  const newsBox = $("newsList");
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

  chart.timeScale().fitContent();
}

async function runSwingScan() {
  $("runSwingBtn").textContent = "Running...";
  try {
    await api("/api/swing/scan", { method: "POST" });
    setTimeout(async () => {
      await loadSwing();
      $("runSwingBtn").textContent = "Run Swing Scan";
    }, 4000);
  } catch (e) {
    $("runSwingBtn").textContent = "Run Swing Scan";
    alert("Swing scan failed: " + e.message);
  }
}

async function refreshAll() {
  await loadHealth();
  await loadRegime();
  await loadSwing();
  await loadRadar();
}

document.addEventListener("DOMContentLoaded", () => {
  $("refreshBtn").addEventListener("click", refreshAll);

  $("loadSymbolBtn").addEventListener("click", () => {
    loadSymbol($("symbolSearch").value);
  });

  $("symbolSearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadSymbol($("symbolSearch").value);
  });

  $("runSwingBtn").addEventListener("click", runSwingScan);

  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(x => x.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  refreshAll();
});