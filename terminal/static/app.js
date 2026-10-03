let chart = null, candleSeries = null, ema10 = null, ema20 = null, ema50 = null, ema200 = null;
const $ = (id) => document.getElementById(id);
let _restoringNavigation = false;
let _symbolRequestId = 0;
window.MODEL_EVENT_SCORE_HELP = "Uncalibrated model score trained on whether the future high reaches +10% within the next 20 trading sessions. It is not a trade win probability or a forecast guarantee.";

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      message = body.detail || body.error || message;
    } catch (e) {}
    throw new Error(message);
  }
  return await res.json();
}
function fmt(v, suffix = "") { return (v === null || v === undefined || Number.isNaN(v)) ? "—" : `${v}${suffix}`; }
function scorePct(v) {
  const n = Number(v);
  return v === null || v === undefined || !Number.isFinite(n)
    ? "—" : `${(n * 100).toFixed(0)}%`;
}
function moneyFmt(v) {
  const n = Number(v);
  return v === null || v === undefined || !Number.isFinite(n)
    ? "—" : `₹${n.toLocaleString()}`;
}
function outcomeBadge(v) { return `<span class="outcome ${v || "PENDING"}">${v || "PENDING"}</span>`; }

function _normalizeView(name) {
  if (name === "overview") return "research";
  return name;
}

function setView(name, options = {}) {
  name = _normalizeView(name);
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active-view"));
  const el = $("view-" + name);
  if (el) el.classList.add("active-view");
  document.querySelectorAll(".nav-btn").forEach(b => {
    const active = _normalizeView(b.dataset.view) === name;
    b.classList.toggle("active", active);
    if (active) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  const titles = {
    funda: "Fundamentals",
    swing: "Swing setups",
    research: "Company research",
    traders: "Trading methods",
    ledger: "Performance",
    league: "Paper league",
    system: "System status",
  };
  const t = $("viewTitle");
  if (t) t.textContent = titles[name] || "NSE Intelligence";
  const subtitle = $("viewSubtitle");
  if (subtitle) {
    const subs = {
      funda: "Long-horizon company quality and valuation research.",
      swing: "Momentum setups and their forward-validation history.",
      research: "Inspect a symbol's chart, setup, model context, and related evidence.",
      traders: "Browse documented methods and their research scans.",
      ledger: "Review graded signals and strategy-run history.",
      league: "Compare methods in historical research and paper trading only.",
      system: "Check service health, data freshness, and source status.",
    };
    subtitle.textContent = subs[name] || "Gabani Stage-2 / VCP Pullback System";
  }
  const overview = $("marketOverview");
  if (overview) overview.classList.toggle("is-collapsed", name !== "research");
  if (name === "research" && chart) setTimeout(() => chart.timeScale().fitContent(), 50);
  if (!options.skipLoad) {
    if (name === "ledger") loadLedger();
    if (name === "research") loadPatterns();
    if (name === "system") {
      loadDeployment();
      loadSourceHealth();
    }
    if (name === "traders" && typeof window.loadTradersIndex === "function") {
      window.loadTradersIndex();
    }
    if (name === "league" && typeof window.loadLeague === "function") {
      window.loadLeague();
    }
  }
  if (options.record !== false && location.hash !== `#${name}`) {
    history.pushState({ view: name }, "", `#${name}`);
  }
}
window.setView = setView;

function _restoreNavigation(skipLoad = false) {
  const [rawView, rawSymbol] = location.hash.slice(1).split("/");
  const view = _normalizeView(rawView || "research");
  _restoringNavigation = true;
  try {
    setView(view, { record: false, skipLoad });
    if (rawSymbol && !skipLoad) loadSymbol(decodeURIComponent(rawSymbol));
  } catch (error) {
    console.warn("Unable to restore terminal navigation:", error);
    setView("research", { record: false });
  } finally {
    _restoringNavigation = false;
  }
}

function _showDataDialog(title, payload) {
  const dialog = $("dataDetailDialog");
  const heading = $("dataDetailTitle");
  const body = $("dataDetailBody");
  const guide = $("methodGuideBody");
  if (!dialog || !heading || !body) return;
  heading.textContent = title || "Data details";
  if (guide) guide.classList.add("hidden");
  body.classList.remove("hidden");
  body.style.display = "";
  body.style.whiteSpace = "";
  body.style.fontFamily = "";
  body.textContent = JSON.stringify(payload, null, 2);
  if (!dialog.open) dialog.showModal();
}

async function _openDataDetail(button) {
  const url = button.dataset.detailUrl;
  if (!url || !url.startsWith("/api/")) return;
  const title = button.dataset.detailTitle || "Data details";
  const dialog = $("dataDetailDialog");
  const heading = $("dataDetailTitle");
  const body = $("dataDetailBody");
  if (!dialog || !heading || !body) return;
  heading.textContent = title;
  body.textContent = "Loading related data…";
  if (!dialog.open) dialog.showModal();
  try {
    const data = await api(url);
    const related = button.dataset.detailRelated;
    const payload = related
      ? { [title]: data, [related]: await api(related) }
      : data;
    body.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    body.textContent = `Could not load ${title}: ${error.message}`;
  }
}

window.openDataDetail = _showDataDialog;
window.openSymbolResearch = function(symbol) {
  setView("research");
  loadSymbol(symbol);
  const chartEl = $("chart");
  if (chartEl) chartEl.scrollIntoView({ behavior: "smooth", block: "start" });
};

async function loadHealth() {
  try {
    const h = await api("/api/health");
    const el = $("healthStatus");
    if (el) el.textContent = `${h.prices_rows.toLocaleString()} price rows`;
  } catch (e) { const el = $("healthStatus"); if (el) el.textContent = `Unavailable: ${e.message}`; }
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
// Top Picks — unified card
// ============================================================
async function loadTopPicks() {
  try {
    const data = await api("/api/toppicks");
    const box = $("picksList");
    if (!box) return;
    if (data.error) throw new Error(data.error);
    box.innerHTML = "";
    (data.picks || []).forEach(x => {
      const subtitle = x.sector || "Unknown sector";
      const primary = `Composite ${scorePct(x.composite)} · event score ${scorePct(x.p_win)}`
        + ` · accumulation ${fmt(x.accum)}`;
      const secondary = `Sector relative strength ${scorePct(x.sector_rs)}`
        + (x.delivery != null ? ` · delivery ${scorePct(x.delivery)}` : "");
      const card = window.renderUnifiedCard({
        symbol: x.symbol,
        setup: !!x.setup,
        subtitle, primary, secondary,
      });
      box.appendChild(card);
    });
  } catch (e) {
    const box = $("picksList");
    if (box) box.textContent = `Research shortlist unavailable: ${e.message}`;
  }
}

// ============================================================
// Swing desk
// ============================================================
async function loadSwing() {
  const tbody = $("swingTable");
  if (!tbody) return;
  try {
    const data = await api("/api/swing/signals");
    tbody.replaceChildren();
    const signals = data.signals || [];
    const score = data.scorecard || {};
    const ms = $("mSignals"); if (ms) ms.textContent = signals.length;
    const mw = $("mWinRate"); if (mw) mw.textContent = data.win_rate == null ? "—" : `${data.win_rate}%`;
    const mo = $("mOpen"); if (mo) mo.textContent = `${score.OPEN || 0} / ${score.PENDING || 0}`;
    for (const s of signals) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${s.date}</td>
        <td><strong>${s.symbol}</strong> ${s.p_win != null ? `<span class="model-score" title="${window.MODEL_EVENT_SCORE_HELP}">Event ${scorePct(s.p_win)}</span>` : ""} ${s.mode === "ALL_WEATHER" ? '<span class="outcome TIMEOUT">All-weather</span>' : ""}</td>
        <td>${fmt(s.trigger)}</td><td>${fmt(s.stop)}</td><td>${fmt(s.target)}</td>
        <td>${fmt(s.risk_pct, "%")}</td>
        <td>${s.pullback ? (s.pullback * 100).toFixed(1) + "%" : "—"}</td>
        <td>${s.impulse ? (s.impulse * 100).toFixed(1) + "%" : "—"}</td>
        <td>${s.ema_zone || "—"}</td>
        <td>${outcomeBadge(s.outcome)}</td>`;
      tr.addEventListener("click", () => { setView("research"); loadSymbol(s.symbol); });
      tbody.appendChild(tr);
    }
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="10">Swing signals unavailable: ${error.message}</td></tr>`;
  }
}

// ============================================================
// Patterns
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
function _checksHtml(checks) {
  if (!checks || !checks.length) {
    return `<p style="color:#7f8da9; font-size:11px; margin:6px 0 0 0;">Conditions not recorded (older tag).</p>`;
  }
  let html = `<div class="checks-list" style="margin-top:8px;">`;
  checks.forEach(c => {
    const icon = c.ok ? "✓" : "✗";
    const colour = c.ok ? "#34d399" : "#fb7185";
    html += `<div class="check-row" style="padding:4px 0; font-size:11px;">
      <span style="color:${colour}; font-weight:bold; min-width:16px; display:inline-block;">${icon}</span>
      <span style="margin-left:6px;">${c.name || c.field || ""}</span>
      <strong style="color:#9fb0cc; float:right; font-weight:400;">${c.got || ""}</strong>
    </div>`;
  });
  html += `</div>`;
  return html;
}
function _safeId(s) {
  return String(s).replace(/[^A-Za-z0-9_-]/g, "_");
}

async function loadPatterns() {
  const list = $("patternList");
  const st = $("patternStatus");
  if (!list) return;
  try {
    const data = await api("/api/patterns/latest?limit=60");
    if (data.error) throw new Error(data.error);
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
      rows.forEach((p, idx) => {
        const div = document.createElement("div");
        div.className = "stock-card";
        div.tabIndex = 0;
        div.setAttribute("role", "button");
        div.setAttribute("aria-label", `Open research for ${p.symbol}`);
        const sauce = sauceLine(p);
        const hasChecks = p.checks && p.checks.length;
        const checkId = `checks-${idx}-${_safeId(p.symbol)}-${_safeId(p.pattern)}`;
        div.innerHTML = `<strong>${p.symbol} · ${(p.pattern || "").replace(/_/g, " ")}</strong>
          <span>${dirBadge(p.direction)} ${statusBadge(p.status)} ${gateBadge(gate[p.pattern])}</span>
          <span>Breakout ₹${p.breakout_level ?? "—"} · Stop ₹${p.stop_level ?? "—"} · Target ₹${p.target_level ?? "—"}</span>
          ${sauce ? `<span>${sauce}</span>` : ""}
          <span>${p.notes || ""}</span>
          ${hasChecks ? `<button class="toggle-btn" data-target="${checkId}">Show conditions (${p.checks.length})</button>
            <div id="${checkId}" class="details-panel hidden">${_checksHtml(p.checks)}</div>`
            : _checksHtml(p.checks)}`;
        div.addEventListener("click", (e) => {
          if (e.target.classList.contains("toggle-btn")) return;
          setView("research");
          loadSymbol(p.symbol);
        });
        div.addEventListener("keydown", (e) => {
          if ((e.key === "Enter" || e.key === " ") && e.target === div) {
            e.preventDefault();
            setView("research");
            loadSymbol(p.symbol);
          }
        });
        list.appendChild(div);
      });
    }
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
        tmatch.map(m => `<div class="stock-card" role="button" tabindex="0"
          aria-label="Open research for ${m.symbol}" data-sym="${m.symbol}"
          style="margin-bottom:8px;"><strong>${m.symbol} · ${(m.template || "").replace(/_/g, " ")}</strong><span>shape similarity ${m.similarity}% · ${m.date}</span></div>`).join("");
      tbox.querySelectorAll(".stock-card").forEach(card => {
        const open = () => {
          setView("research");
          loadSymbol(card.dataset.sym);
        };
        card.addEventListener("click", open);
        card.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            open();
          }
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
    if (st) st.innerHTML = `<span>Status</span><strong>scan running in background — click Refresh afterwards</strong>`;
    setTimeout(loadPatterns, 60000);
  } catch (e) {
    if (st) st.innerHTML = `<span>Status</span><strong>scan start failed: ${e.message}</strong>`;
  }
  if (btn) btn.textContent = "Run Full Scan";
}

async function startSwingScan() {
  const btn = $("runSwingBtn");
  const status = $("swingScanStatus");
  if (btn) { btn.disabled = true; btn.textContent = "Starting…"; }
  if (status) status.textContent = "Requesting the scan…";
  try {
    const started = await api("/api/swing/scan", { method: "POST" });
    if (started.already_running) {
      if (status) status.textContent = "A swing scan is already running; checking its status.";
    } else if (!started.started) {
      throw new Error("The swing scan did not start.");
    }
    if (btn) btn.textContent = "Scanning…";
    for (let attempt = 0; attempt < 180; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      const result = await api("/api/swing/scan/status");
      if (status) status.textContent = result.message || "Swing scan is running…";
      if (!result.running) {
        if (result.status === "error") throw new Error(result.message);
        await refreshAll();
        return;
      }
    }
    if (status) status.textContent = "Still running; use Refresh after the scan finishes.";
  } catch (error) {
    if (status) status.textContent = `Swing scan failed: ${error.message}`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Run Swing Scan"; }
  }
}

async function runScreener() {
  const button = $("runScreenerBtn");
  const metrics = $("screenerMetrics");
  const checks = $("screenerChecks");
  const chartSymbol = (($("chartTitle") || {}).textContent || "")
    .split(" ")[0];
  const enteredSymbol = (($("symbolSearch") || {}).value || "").trim();
  const symbol = (enteredSymbol || (chartSymbol !== "Chart" ? chartSymbol : ""))
    .trim().toUpperCase();
  if (!metrics || !checks) return;
  if (!symbol) {
    metrics.textContent = "Enter a symbol in the search field first.";
    return;
  }
  if (button) { button.disabled = true; button.textContent = "Checking…"; }
  metrics.textContent = `Checking ${symbol}…`;
  checks.textContent = "Loading rule results…";
  try {
    const data = await api(`/api/screener/${encodeURIComponent(symbol)}`);
    if (data.error) throw new Error(data.error);
    metrics.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `${symbol} · ${data.overall_signal ? "all baseline and setup checks passed" : "not all checks passed"}`;
    metrics.appendChild(heading);
    const source = document.createElement("p");
    source.className = "method-note";
    source.textContent = `${data.source || "Source unavailable"} · latest bar ${data.as_of || "date unavailable"}`;
    metrics.appendChild(source);
    [
      ["Latest price", data.current_price],
      ["EMA 200", data.ema_200],
      ["1-month momentum", data.momentum_1m],
      ["3-month momentum", data.momentum_3m],
      ["52-week high proximity", data.proximity_52w],
      ["Impulse", data.impulse_gain],
      ["Pullback", data.pullback_depth],
      ["Sessions since high", data.days_since_high],
      ["Recent range", data.tightness_pct],
    ].forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "level";
      const left = document.createElement("span");
      left.textContent = label;
      const right = document.createElement("strong");
      right.textContent = value == null ? "—" : String(value);
      row.append(left, right);
      metrics.appendChild(row);
    });
    checks.replaceChildren();
    const resultTitle = document.createElement("h3");
    resultTitle.textContent = "Rule checks";
    checks.appendChild(resultTitle);
    Object.entries(data.checks || {}).forEach(([name, passed]) => {
      const row = document.createElement("div");
      row.className = "level";
      const left = document.createElement("span");
      left.textContent = name;
      const right = document.createElement("strong");
      right.textContent = passed ? "Passed" : "Not passed";
      row.append(left, right);
      checks.appendChild(row);
    });
    const note = document.createElement("p");
    note.className = "method-note";
    note.textContent = "Screening result only; not a forecast or trade instruction.";
    checks.appendChild(note);
  } catch (error) {
    metrics.textContent = `Screener unavailable: ${error.message}`;
    checks.textContent = "No rule results were returned.";
  } finally {
    if (button) { button.disabled = false; button.textContent = "Run Screener"; }
  }
}

// ============================================================
// Radar
// ============================================================
async function loadRadar() {
  try {
    const data = await api("/api/radar");
    const mu = $("mUniverse"); if (mu) mu.textContent = data.total || "—";
    const g = data.groups || {};
    const render = (items, box) => {
      if (!box) return;
      box.innerHTML = "";
      (items || []).slice(0, 18).forEach(x => {
        const subtitle = `1M ${fmt(x.perf1m, "%")} · 3M ${fmt(x.perf3m, "%")} · Vol ${fmt(x.relvol, "x")}`;
        const primary = `₹${fmt(x.mcap_cr)} cr mcap`;
        const secondary = x.p_win != null
          ? `Model event score ${scorePct(x.p_win)} · uncalibrated` : "";
        box.appendChild(window.renderUnifiedCard({
          symbol: x.symbol, subtitle, primary, secondary,
        }));
      });
    };
    render(g["Momentum"], $("radarMomentum"));
    render(g["Volume Spike"], $("radarVolume"));
    render(g["Turnaround"], $("radarTurn"));
  } catch (e) {
    ["radarMomentum", "radarVolume", "radarTurn"].forEach(id => {
      const box = $(id);
      if (box) box.textContent = `Radar data unavailable: ${e.message}`;
    });
  }
}

// ============================================================
// Compare
// ============================================================
async function runCompare() {
  const input = $("compareInput");
  const box = $("compareBox");
  if (!input || !box) return;
  const syms = input.value.split(",").map(s => s.trim().toUpperCase()).filter(Boolean);
  if (syms.length < 2) {
    box.innerHTML = "<p>Enter at least 2 symbols, comma-separated.</p>";
    return;
  }
  if (syms.length > 4) {
    box.innerHTML = "<p>Max 4 symbols.</p>";
    return;
  }
  box.innerHTML = "<p>Loading...</p>";
  try {
    const r = await api(`/api/compare?symbols=${encodeURIComponent(syms.join(","))}`);
    window.renderCompareTable(r);
  } catch (e) {
    box.innerHTML = `<p>Compare error: ${e.message}</p>`;
  }
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
// Deployment
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

async function loadSourceHealth() {
  const box = $("sourceHealthBox");
  if (!box) return;
  box.textContent = "Loading data-source health...";
  try {
    const data = await api("/api/sources");
    const sources = data.sources || [];
    box.replaceChildren();
    if (!sources.length) {
      box.textContent = "No source adapters are registered.";
      return;
    }
    sources.forEach(source => {
      const row = document.createElement("div");
      row.className = "level";
      row.style.padding = "8px 12px";
      const name = document.createElement("strong");
      name.textContent = source.provider;
      const details = document.createElement("span");
      details.style.cssText = "flex:1; margin-left:12px; color:#9fb0cc";
      details.textContent = `${source.state} · rate limit ${source.rate_limit_ok ? "available" : "reached"} · ${source.calls} calls / ${source.failures} failures`;
      row.append(name, details);
      if (source.last_error) {
        const error = document.createElement("small");
        error.style.cssText = "display:block; color:#fb7185; margin-left:12px";
        error.textContent = source.last_error;
        row.appendChild(error);
      }
      box.appendChild(row);
    });
  } catch (error) {
    box.textContent = `Data-source health unavailable: ${error.message}`;
  }
}

// ============================================================
// Chart
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
  chart.subscribeClick((param) => {
    if (!param || !param.time || !param.seriesData) return;
    const candle = param.seriesData.get(candleSeries);
    if (!candle) return;
    _showDataDialog("Selected chart candle", {
      symbol: ($("chartTitle")?.textContent || "").split(" ")[0],
      date: param.time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    });
  });
}

async function _applyPatternMarkers(symbol) {
  if (!candleSeries) return;
  try {
    const h = await api(`/api/patterns/history/${symbol}?limit=500`);
    const sigs = (h && h.signals) || [];
    if (!sigs.length) {
      candleSeries.setMarkers([]);
      return;
    }
    const markers = sigs.map(s => {
      const d = String(s.date).slice(0, 10);
      let color = "#fbbf24";
      let position = "aboveBar";
      let shape = "circle";
      let text = s.pattern ? s.pattern.slice(0, 6) : "";
      if (s.outcome === "WIN") { color = "#34d399"; shape = "arrowUp"; position = "belowBar"; }
      else if (s.outcome === "LOSS") { color = "#fb7185"; shape = "arrowDown"; position = "aboveBar"; }
      else if (s.outcome === "EXPIRED" || s.outcome === "TIMEOUT") { color = "#fbbf24"; shape = "circle"; }
      else { color = "#60a5fa"; shape = "square"; }
      if (s.direction === "BEARISH") {
        shape = "arrowDown";
        position = "aboveBar";
        if (s.outcome === "LOSS") color = "#34d399";
      }
      return { time: d, position, color, shape, text, size: 0.8 };
    });
    candleSeries.setMarkers(markers);
  } catch (e) {}
}

async function loadSymbol(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) return;
  const requestId = ++_symbolRequestId;
  const search = $("symbolSearch");
  if (search) search.value = symbol;
  if (!_restoringNavigation) {
    const nextHash = `#research/${encodeURIComponent(symbol)}`;
    if (location.hash !== nextHash) {
      history.pushState({ view: "research", symbol }, "", nextHash);
    }
  }
  const titleEl = $("chartTitle");
  const subEl = $("chartSubtitle");
  if (titleEl) titleEl.textContent = `${symbol} — Inspector`;
  if (subEl) subEl.textContent = "Loading chart...";
  let chartData, summary;
  try {
    chartData = await api(`/api/cockpit/${symbol}/chart`);
    summary = await api(`/api/cockpit/${symbol}/summary`);
  } catch (e) {
    if (requestId === _symbolRequestId && subEl) {
      subEl.textContent = `Load failed: ${e.message}`;
    }
    return;
  }
  if (requestId !== _symbolRequestId) return;
  resetChart();
  if (!chartData.candles || chartData.candles.length === 0) {
    if (subEl) subEl.textContent = "No price history found.";
    renderStockPulse(symbol, []);
    if (window.loadResearch) window.loadResearch(symbol);
    if (window.loadTraderMatches) window.loadTraderMatches(symbol);
    const setupBadge = $("setupBadge");
    const setupSummary = $("setupSummary");
    if (setupBadge) { setupBadge.className = "badge"; setupBadge.textContent = "No history"; }
    if (setupSummary) setupSummary.textContent = "No stored price history.";
    return;
  }
  candleSeries.setData(chartData.candles);
  ema10.setData(chartData.ema10 || []);
  ema20.setData(chartData.ema20 || []);
  ema50.setData(chartData.ema50 || []);
  ema200.setData(chartData.ema200 || []);
  if (subEl) subEl.textContent = `${summary.sector || "Unknown sector"} · ₹${fmt(summary.mcap_cr)} cr · Fund ${fmt(summary.fund_score)}`;
  renderStockPulse(symbol, chartData.candles);
  if (window.loadResearch) window.loadResearch(symbol);
  if (window.loadTraderMatches) window.loadTraderMatches(symbol);

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
  try {
    const meta = await api(`/api/meta/${symbol}`);
    if (meta && meta.p_win != null && setupSummary) {
      const why = (meta.why || []).map(w => `<div class="level"><span>why · ${w.feature}</span><strong>${w.impact > 0 ? "+" : ""}${w.impact}</strong></div>`).join("");
      const whyBlock = why
        ? `<button class="toggle-btn" data-target="shapDetails">Show model feature contributions</button>
           <div id="shapDetails" class="details-panel hidden">
             <div class="level"><span>Uncalibrated event score</span><strong>${scorePct(meta.p_win)}</strong></div>
             <p class="method-note">Feature contributions describe this model output; they are not causal explanations.</p>
             ${why}
           </div>`
        : "";
      setupSummary.insertAdjacentHTML("beforeend", `
        <div class="model-explainer" title="${window.MODEL_EVENT_SCORE_HELP}">
          <div class="level"><span>Model event score</span><strong>${scorePct(meta.p_win)}</strong></div>
          <p class="method-note">${window.MODEL_EVENT_SCORE_HELP}</p>
        </div>${whyBlock}`);
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
        div.tabIndex = 0;
        div.setAttribute("role", "button");
        div.setAttribute("aria-label", `Open news details: ${n.title}`);
        div.textContent = `[${n.age_days}d] ${n.label || "neutral"} — ${n.title}`;
        const open = () => _showDataDialog("Stored news item", {
          ...n,
          source_url: null,
          note: "No source URL was stored with this news item.",
        });
        div.addEventListener("click", open);
        div.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            open();
          }
        });
        newsBox.appendChild(div);
      });
    } else {
      newsBox.textContent = "No stored news.";
    }
  }
  await _applyPatternMarkers(symbol);
  if (requestId !== _symbolRequestId) return;
  if (chart) chart.timeScale().fitContent();
}
window.loadSymbol = loadSymbol;

function renderStockPulse(symbol, candles) {
  const box = $("stockPulse");
  if (!box) return;
  const bars = candles || [];
  const last = bars[bars.length - 1];
  const previous = bars[bars.length - 2];
  if (!last) {
    box.textContent = `${symbol}: no stored daily bars are available.`;
    return;
  }
  const close = Number(last.close);
  const change = (lookback) => {
    const base = bars.length > lookback ? Number(bars[bars.length - lookback - 1].close) : null;
    return base > 0 ? (close / base - 1) * 100 : null;
  };
  const daily = previous && Number(previous.close) > 0
    ? (close / Number(previous.close) - 1) * 100 : null;
  const fmtPct = value => value == null || !Number.isFinite(value)
    ? "insufficient bars" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
  const latestLine = (label, value) => `
    <div class="level"><span>${label}</span><strong>${value}</strong></div>`;
  const calcEma = period => {
    if (bars.length < period) return null;
    const alpha = 2 / (period + 1);
    let value = Number(bars[0].close);
    for (let i = 1; i < bars.length; i++) {
      value = Number(bars[i].close) * alpha + value * (1 - alpha);
    }
    return value;
  };
  const emaSeries = {
    "EMA 20": calcEma(20),
    "EMA 50": calcEma(50),
    "EMA 200": calcEma(200),
  };
  const available = Object.entries(emaSeries)
    .filter(([, value]) => value != null && Number.isFinite(Number(value)));
  const trend = available.length
    ? available.map(([name, value]) =>
      `${close >= Number(value) ? "above" : "below"} ${name}`).join(" · ")
    : "EMA context unavailable";
  box.innerHTML = `
    <div class="level"><span>Latest stored close · ${last.time}</span><strong>₹${close.toFixed(2)}</strong></div>
    ${latestLine("1-session change", fmtPct(daily))}
    ${latestLine("20-session change", fmtPct(change(20)))}
    ${latestLine("60-session change", fmtPct(change(60)))}
    ${latestLine("Trend context", trend)}
    <p class="method-note">Daily end-of-day data only. This describes recent price behaviour; it does not predict the next move. Source bar date: ${last.time}.</p>`;
}

// ============================================================
// Sizing / Delivery
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
  let compact, details;
  if (sz.error) {
    compact = `<div class="level"><span>Sizing</span><strong>unavailable yet</strong></div>`;
    details = capitalEditor(sz.capital);
  } else if (sz.shares !== undefined) {
    const allocatedPct = sz.actual_alloc_pct ?? sz.alloc_pct;
    const plannedRiskPct = sz.actual_planned_risk_pct ?? sz.risk_pct;
    compact = `<div class="level"><span>Research position size</span><strong>${moneyFmt(sz.suggested_value)} (${fmt(allocatedPct, "%")})</strong></div>
      <div class="level"><span>Quantity at trigger</span><strong>${sz.shares} shares${sz.actionable === false ? " (not actionable)" : ""}</strong></div>`;
    details = `
      <div class="level"><span>Capital</span><strong>${moneyFmt(sz.capital)}</strong></div>
      <div class="level"><span>Planned stop-risk budget</span><strong>${fmt(sz.planned_risk_budget_pct ?? sz.risk_per_trade_pct, "%")}</strong></div>
      <div class="level"><span>Regime adjustment</span><strong>${sz.regime_level || "—"} · ×${fmt(sz.regime_mult)}</strong></div>
      <div class="level"><span>Shape adjustment</span><strong>${fmt(sz.shape_score)} / 100 · ×${fmt(sz.quality_mult)}</strong></div>
      <div class="level"><span>Planned loss at stop</span><strong>${moneyFmt(sz.risk_amount)} (${fmt(plannedRiskPct, "%")})</strong></div>
      <div class="level"><span>Limiting rule</span><strong>${sz.binding_cap || "—"}</strong></div>
      <p class="method-note">${sz.risk_note || "Fixed-risk research sizing. No calibrated trade win probability or Kelly input is used. Quantity is limited by planned stop risk and maximum allocation; gaps, slippage, fees, and taxes can increase losses."}</p>
      ${sz.reason ? `<p class="method-warning">${sz.reason}</p>` : ""}`;
  } else {
    compact = `<div class="level"><span>Suggested allocation</span><strong>${fmt(sz.alloc_pct, "%")} of capital</strong></div>`;
    details = `
      <div class="level"><span>Capital</span><strong>${moneyFmt(sz.capital)}</strong></div>
      <div class="level"><span>Planned stop-risk budget</span><strong>${fmt(sz.planned_risk_budget_pct ?? sz.risk_per_trade_pct, "%")}</strong></div>
      <div class="level"><span>Regime adjustment</span><strong>${sz.regime_level || "—"} · ×${fmt(sz.regime_mult)}</strong></div>
      <div class="level"><span>Shape adjustment</span><strong>${fmt(sz.shape_score)} / 100 · ×${fmt(sz.quality_mult)}</strong></div>
      <p class="method-note">${sz.risk_note || "Fixed-risk research sizing; no calibrated trade win probability or Kelly input is used. Planned stop risk can be exceeded by gaps, slippage, fees, and taxes."}</p>
      ${sz.reason ? `<p class="method-warning">${sz.reason}</p>` : ""}`;
  }
  box.innerHTML = `
    <h3 style="margin:0;font-size:15px;">Position sizing (research estimate)</h3>
    ${compact}
    <button class="toggle-btn" data-target="sizingDetails">Show sizing inputs and limits</button>
    <div id="sizingDetails" class="details-panel hidden">
      ${details}
      ${capitalEditor(sz.capital)}
    </div>`;
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

document.addEventListener("click", (e) => {
  const detail = e.target.closest("[data-detail-url]");
  if (detail) {
    e.preventDefault();
    _openDataDetail(detail);
    return;
  }
  const viewButton = e.target.closest("[data-view]");
  if (viewButton) {
    e.preventDefault();
    setView(viewButton.dataset.view);
    const loader = viewButton.dataset.load;
    if (loader === "research-universe" && window.loadResearchUniverse) {
      window.loadResearchUniverse(false);
    }
    const targetId = viewButton.dataset.scrollTarget;
    if (targetId) {
      requestAnimationFrame(() => {
        const target = $(targetId);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    return;
  }
  const btn = e.target.closest(".toggle-btn");
  if (btn) {
    e.preventDefault();
    e.stopPropagation();
    const target = btn.dataset.target;
    if (target) {
      const el = document.getElementById(target);
      if (el) el.classList.toggle("hidden");
    }
  }
});

// ============================================================
// Init
// ============================================================
async function refreshAll(initialLoad = false) {
  const button = $("refreshBtn");
  const status = $("refreshStatus");
  if (button) { button.disabled = true; button.textContent = "Refreshing…"; }
  if (status) status.textContent = "Reloading latest saved data…";
  const tasks = [
    loadHealth, loadRegime, loadTopPicks, loadSwing,
    loadPatterns, loadRadar, loadDeployment, loadSourceHealth,
  ];
  [
    window.refreshScannerPanels,
    window.refreshStrategyLists,
    window.loadStrategyRuns,
    window.loadResearchUniverse,
    window.loadResearchSectors,
  ].forEach(fn => { if (typeof fn === "function") tasks.push(fn); });
  const [rawView, rawSymbol] = location.hash.slice(1).split("/");
  const view = _normalizeView(rawView);
  if (initialLoad) {
    if (view === "ledger") tasks.push(loadLedger);
    if (view === "traders" && window.loadTradersIndex) {
      tasks.push(window.loadTradersIndex);
    }
    if (view === "league" && window.loadLeague) {
      tasks.push(window.loadLeague);
    }
  }
  const symbol = rawSymbol ? decodeURIComponent(rawSymbol) :
    (($("chartTitle")?.textContent || "").split(" ")[0] || "");
  if (_normalizeView(rawView) === "research" && symbol &&
      symbol !== "Chart") {
    tasks.push(() => loadSymbol(symbol));
  }
  try {
    const results = await Promise.allSettled(
      tasks.map(task => Promise.resolve().then(task)));
    const failures = results.filter(result => result.status === "rejected");
    if (status) {
      status.textContent = failures.length
        ? `Reload completed with ${failures.length} request errors. See affected panels.`
        : "Latest saved data reloaded. Use scan buttons to compute new results.";
    }
  } finally {
    if (button) { button.disabled = false; button.textContent = "Refresh"; }
  }
}
document.addEventListener("DOMContentLoaded", () => {
  const closeDetails = $("dataDetailClose");
  if (closeDetails) {
    closeDetails.addEventListener("click", () => $("dataDetailDialog").close());
  }
  const rb = $("refreshBtn");
  if (rb) rb.addEventListener("click", refreshAll);
  const sourceHealthBtn = $("refreshSourceHealthBtn");
  if (sourceHealthBtn) {
    sourceHealthBtn.addEventListener("click", loadSourceHealth);
  }
  const lsb = $("loadSymbolBtn");
  if (lsb) lsb.addEventListener("click", () => {
    setView("research");
    loadSymbol($("symbolSearch").value);
  });
  const ss = $("symbolSearch");
  if (ss) ss.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { setView("research"); loadSymbol(ss.value); }
  });
  const rps = $("runPatternScan");
  if (rps) rps.addEventListener("click", runPatternScan);
  const swingScanBtn = $("runSwingBtn");
  if (swingScanBtn) swingScanBtn.addEventListener("click", startSwingScan);
  const screenerBtn = $("runScreenerBtn");
  if (screenerBtn) screenerBtn.addEventListener("click", runScreener);
  window.runScreener = runScreener;
  const rrb = $("runResearchBtn");
  if (rrb) rrb.addEventListener("click", () => {
    const titleEl = $("chartTitle");
    const sym = (titleEl ? titleEl.textContent : "").split(" ")[0];
    if (sym && window.loadResearch) window.loadResearch(sym);
  });
  const cmpBtn = $("compareRunBtn");
  if (cmpBtn) cmpBtn.addEventListener("click", runCompare);
  const cmpIn = $("compareInput");
  if (cmpIn) cmpIn.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runCompare();
  });
  window.addEventListener("popstate", _restoreNavigation);
  _restoreNavigation(true);
  refreshAll(true);
});
