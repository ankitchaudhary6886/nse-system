let chart = null, candleSeries = null, ema10 = null, ema20 = null, ema50 = null, ema200 = null;
let sma10 = null, sma20 = null;
/* Second chart instance = the RSI pane. lightweight-charts 4.1.3 shipped here
   has no pane API (no `addPane`/`panes` in the standalone bundle), so the two
   panes are two charts in two flex cells with their time axes mirrored. */
let rsiChart = null, rsiSeries = null, rsiBand = null, rsiReady = false;
let rsiLevelLines = [];
let _chartCandleByTime = new Map();
let _chartEmaByTime = new Map();
let _chartRsiByTime = new Map();
let _chartLastBar = null;
let _chartLastRsi = null;
let _maData = {};
let _paneSync = false;
const $ = (id) => document.getElementById(id);
let _restoringNavigation = false;
let _symbolRequestId = 0;
window.MODEL_EVENT_SCORE_HELP = "A machine estimate of how likely this company is to rise at least 10% at some point in the next month of trading. It is a rough lean, not a forecast, and not the same as the odds of a trade working out.";

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

/** Update a compact status row (the "Status" lines above lists) with a tone. */
function setStatusRow(el, value, tone) {
  if (!el) return;
  const t = tone === "bull" || tone === "bear" || tone === "neut" ? tone : "info";
  const color = t === "bull" ? "var(--fx-bull)" : t === "bear" ? "var(--fx-bear)"
    : t === "neut" ? "var(--fx-neut)" : "var(--fx-info)";
  el.innerHTML = `<span class="fx-k"><span class="fx-dot${t === "info" ? " pulse" : ""}"`
    + ` style="background:${color}"></span>Status</span>`
    + `<span class="fx-v ${t === "bull" ? "is-bull" : t === "bear" ? "is-bear" : t === "neut" ? "is-neut" : "is-mut"}">${value}</span>`;
}
window.setStatusRow = setStatusRow;


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

// Status pills replace raw text alerts: one line, a pulse dot, mono figures.
function fxPill(tone, label, value, opts) {
  const o = opts || {};
  const cls = tone === "bull" ? "bull" : tone === "bear" ? "bear" : tone === "neut" ? "neut" : "info";
  const dot = o.pulse
    ? `<span class="fx-dot pulse"></span>`
    : `<span class="fx-dot" style="opacity:.7"></span>`;
  const val = value == null || value === ""
    ? ""
    : `<span class="fx-fig" style="font-size:12px;color:inherit">${value}</span>`;
  return `<span class="fx-chip ${cls}${o.sans ? " mono-sans" : ""}"${o.title ? ` title="${o.title}"` : ""}>`
    + `${dot}${label ? `<span>${label}</span>` : ""}${val}</span>`;
}
/** Numeric-only pill: green when positive, rose when negative, amber for zero. */
function fxNumPill(label, value, opts) {
  const o = opts || {};
  const n = Number(value);
  const tone = !Number.isFinite(n) ? "neut" : n > 0 ? "bull" : n < 0 ? "bear" : "neut";
  const shown = Number.isFinite(n) ? `${n > 0 ? "+" : ""}${n.toFixed(o.dp == null ? 0 : o.dp)}` : "—";
  return fxPill(tone, label, shown, { title: o.title, pulse: o.pulse });
}
window.fxPill = fxPill;
window.fxNumPill = fxNumPill;

async function loadRegime() {
  const box = $("regimeBanner");
  if (!box) return;
  try {
    const r = await api("/api/regime");
    box.classList.remove("loading", "bull", "defensive");
    /* Stance -> tone. Word first, then the evidence, then what we would do. */
    const STANCE = {
      STRONG_BULL: { tone: "bull", pulse: true, size: "×1.0", note: "full size" },
      BULL: { tone: "bull", pulse: true, size: "×1.0", note: "full size" },
      NEUTRAL: { tone: "neut", pulse: false, size: "×0.75", note: "smaller size" },
      WEAK: { tone: "bear", pulse: false, size: "×0.5", note: "smaller size, defensive only" },
      CAPITULATION: { tone: "bear", pulse: true, size: "×0.25", note: "minimum size, defensive only" },
    };
    const s = STANCE[r.stance];
    let html = "";
    if (s) {
      if (s.tone === "bull") box.classList.add("bull");
      if (s.tone === "bear") box.classList.add("defensive");
      const zone = r.stance === "NEUTRAL" ? "vs" : (String(r.stance).includes("BULL") ? ">" : "<");
      html = `<div class="fx-banner ${s.tone}">
        ${fxPill(s.tone, r.stance, null, { pulse: s.pulse, sans: true })}
        ${fxPill("", `${r.symbol} close`, fmt(r.index_close), { title: "Index close used for the regime read" })}
        ${fxPill("", `EMA10 ${zone}`, fmt(r.ema10), { title: "The 10-session average of the index close" })}
        ${fxPill(s.tone, "Size", s.size, { title: `Regime size guidance: ${s.note}` })}
      </div>`;
    } else {
      html = `<div class="fx-banner neut">${fxPill("neut", "Regime unavailable", null, { sans: true })}
        <span class="fx-chip mono-sans">${r.error || "no read returned"}</span></div>`;
    }
    let flow = null;
    try {
      const m = await api("/api/macro");
      if (m && m.fii_net !== null && m.dii_net !== null) flow = m;
    } catch (e) {}
    if (flow) {
      html += `<div class="fx-banner" style="margin-top:8px">
        ${fxNumPill("FII", flow.fii_net, { dp: 0, title: "Foreign institutional net flow, rupees crore" })}
        ${fxNumPill("DII", flow.dii_net, { dp: 0, title: "Domestic institutional net flow, rupees crore" })}
        ${fxNumPill("Net", flow.net_flow, { dp: 0, pulse: true, title: "FII + DII net flow, rupees crore" })}
        <span class="fx-chip mono-sans" style="color:var(--fx-zinc-500)">Smart money · ₹ cr</span>
      </div>`;
    }
    box.innerHTML = html;
  } catch (e) {
    box.classList.add("defensive");
    box.innerHTML = `<div class="fx-banner neut">${fxPill("neut", "Regime API unavailable", null, { sans: true })}</div>`;
  }
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
      /* Plain "label value" pairs separated by · — the card renderer turns them
         into mono key/value cells. No markup in the data path. */
      const primary = `Rank ${scorePct(x.composite)} · Event ${scorePct(x.p_win)}`
        + ` · Accum ${fmt(x.accum)}`;
      const secondary = `Sector RS ${scorePct(x.sector_rs)}`
        + (x.delivery != null ? ` · Delivery ${scorePct(x.delivery)}` : "");
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
        <td>${fmt(s.trigger)}</td>
        <td><span data-explain="stop" data-explain-stop title="Click to learn what this is">${fmt(s.stop)}</span></td>
        <td><span data-explain="target" data-explain-stop title="Click to learn what this is">${fmt(s.target)}</span></td>
        <td><span data-explain="risk_pct" data-explain-stop title="Click to learn what this is">${fmt(s.risk_pct, "%")}</span></td>
        <td><span data-explain="pullback" data-explain-stop title="Click to learn what this is">${s.pullback ? (s.pullback * 100).toFixed(1) + "%" : "—"}</span></td>
        <td><span data-explain="impulse" data-explain-stop title="Click to learn what this is">${s.impulse ? (s.impulse * 100).toFixed(1) + "%" : "—"}</span></td>
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
    if (st) setStatusRow(st,
      `${rows.length}${rows.length ? " · latest " + rows[0].date : ""} · gate ${en} ON / ${pr} PROV / ${di} OFF`,
      rows.length ? "bull" : "neut");
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
        const subtitle = x.sector || "";
        const primary = `Mcap ₹${fmt(x.mcap_cr)}cr`
          + (x.p_win != null ? ` · Event ${scorePct(x.p_win)}` : "");
        const secondary = `1M ${fmt(x.perf1m, "%")} · 3M ${fmt(x.perf3m, "%")}`
          + ` · Vol ${fmt(x.relvol, "x")}`;
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
        <div class="fx-row"><span>Ideas Recorded</span><strong>${stats.total_trades}</strong></div>
        <div class="fx-row"><span>Wins / Losses</span><strong>${stats.wins} / ${stats.losses}</strong></div>
        <div class="fx-row">${_ledgerLabel("Win Rate", "signal")}<strong>${fmt(stats.win_rate, "%")}</strong></div>
        <div class="fx-row">${_ledgerLabel("Profit per unit lost", "profit_factor")}<strong>${stats.profit_factor}</strong></div>
        <div class="fx-row">${_ledgerLabel("Average result per idea", "expectancy")}<strong>${fmt(stats.expectancy_r)}R</strong></div>
        <div class="fx-row">${_ledgerLabel("Total return", "r_multiple")}<strong>${fmt(stats.total_r)}R</strong></div>
        <div class="fx-row">${_ledgerLabel("Worst fall from a peak", "max_drawdown")}<strong>${fmt(stats.max_drawdown_r)}R</strong></div>`;
    }
    const rows = (trades && trades.trades) || [];
    const tbody = $("ledgerTable");
    if (tbody) {
      tbody.innerHTML = "";
      rows.forEach(t => {
        const tr = document.createElement("tr");
        tr.className = "click-row";
        tr.tabIndex = 0;
        tr.setAttribute("role", "button");
        tr.setAttribute("aria-label", `Open research for ${t.symbol}`);
        tr.innerHTML = `<td>${t.date}</td>
          <td><strong>${t.symbol}</strong></td>
          <td>${fmt(t.trigger)}</td>
          <td>${fmt(t.stop)}</td>
          <td>${fmt(t.target)}</td>
          <td>${outcomeBadge(t.outcome)}<span class="ledger-outcome-words">${_outcomeWords(t.outcome)}</span></td>
          <td>${_ledgerRText(t)}</td>`;
        tr.addEventListener("click", () => { setView("research"); loadSymbol(t.symbol); });
        tbody.appendChild(tr);
      });
    }
    _renderLedgerCompanies(rows);
  } catch (e) { const box = $("ledgerStats"); if (box) box.innerHTML = `<p>Error loading ledger: ${e.message}</p>`; }
}

// ============================================================
// Ledger - companies that worked / companies that did not
//
// WHY: "wins 6 / losses 4" says nothing about WHICH companies. The owner
// asked for the names, in words, newest first, each one clickable through to
// that company's research page. R is spelled out rather than left as a bare
// letter (see explain.py -> r_multiple).
// ============================================================
const LEDGER_LIST_CAP = 6;
let _ledgerCompaniesTrades = [];
let _ledgerListOpen = { worked: false, failed: false };

function _ledgerSight(key, label) {
  return `<span class="ledger-sight" data-explain="${key}" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does ${label} mean?">?</span>`;
}
function _ledgerLabel(label, key) {
  return `<span>${label}${_ledgerSight(key, label)}</span>`;
}
function _outcomeWords(outcome) {
  switch (outcome) {
    case "WIN": return "reached the goal";
    case "LOSS": return "hit the safety line";
    case "TIMEOUT": return "ran out of time, flat";
    case "EXPIRED": return "nothing happened in time";
    case "OPEN": return "still running";
    case "PENDING": return "waiting to start";
    default: return "not graded yet";
  }
}
function _ledgerRText(t) {
  const r = t.r_multiple;
  if (r === null || r === undefined || !Number.isFinite(Number(r))) {
    // No R yet: show what 1R was going to be, in plain words.
    const riskPct = Number(t.risk_pct);
    return Number.isFinite(riskPct)
      ? `<span class="ledger-r-risk">1R was ${riskPct}%</span>${_ledgerSight("r_multiple", "1R")}`
      : `<span class="ledger-r-risk">not graded</span>`;
  }
  const n = Number(r);
  const txt = `${n > 0 ? "+" : ""}${n}R`;
  const cls = n > 0 ? "ledger-r good" : (n < 0 ? "ledger-r bad" : "ledger-r flat");
  return `<span class="${cls}">${txt}</span>${_ledgerSight("r_multiple", "R")}`;
}
function _ledgerCompanyRow(t) {
  const tr = document.createElement("tr");
  tr.className = "click-row";
  tr.tabIndex = 0;
  tr.setAttribute("role", "button");
  tr.setAttribute("aria-label", `Open research for ${t.symbol}`);
  tr.innerHTML = `<td><strong>${t.symbol}</strong></td>
    <td>${t.date}</td>
    <td><span class="ledger-words">${_outcomeWords(t.outcome)}</span></td>
    <td>${outcomeBadge(t.outcome)}</td>
    <td>${_ledgerRText(t)}</td>`;
  tr.addEventListener("click", () => { setView("research"); loadSymbol(t.symbol); });
  tr.addEventListener("keydown", ev => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      setView("research"); loadSymbol(t.symbol);
    }
  });
  return tr;
}
function _ledgerCompanyColumn(id, wantOutcomes, emptyText) {
  const all = _ledgerCompaniesTrades.filter(t => wantOutcomes.indexOf(t.outcome) !== -1);
  const open = !!_ledgerListOpen[id];
  const shown = open ? all : all.slice(0, LEDGER_LIST_CAP);
  const body = document.createElement("div");
  body.className = "ledger-company-body";
  if (!all.length) {
    const p = document.createElement("p");
    p.className = "ledger-list-empty";
    p.textContent = emptyText;
    body.appendChild(p);
    return body;
  }
  const table = document.createElement("table");
  table.className = "ledger-company-table";
  table.innerHTML = `<thead><tr><th>Company</th><th>Date</th><th>What happened</th><th>Result</th><th>Profit / loss</th></tr></thead>`;
  const tb = document.createElement("tbody");
  shown.forEach(t => tb.appendChild(_ledgerCompanyRow(t)));
  table.appendChild(tb);
  body.appendChild(table);
  if (all.length > LEDGER_LIST_CAP) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "ledger-more";
    more.textContent = open
      ? "Show fewer"
      : `Show all ${all.length}`;
    more.addEventListener("click", () => {
      _ledgerListOpen[id] = !_ledgerListOpen[id];
      _renderLedgerCompanies(_ledgerCompaniesTrades);
    });
    body.appendChild(more);
  }
  return body;
}
function _renderLedgerCompanies(trades) {
  const host = $("ledgerCompanies");
  if (!host) return;
  _ledgerCompaniesTrades = (trades || []).slice().sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  host.replaceChildren();

  const head = document.createElement("div");
  head.className = "panel-header";
  head.innerHTML = `<div>
      <h2 class="panel-title">Which companies worked, and which did not</h2>
      <p>Every company we recorded a buy idea for, newest first. Click any name to open that company's research page.</p>
    </div>
    <span class="badge muted">${_ledgerCompaniesTrades.length} recorded</span>`;
  host.appendChild(head);

  const grid = document.createElement("div");
  grid.className = "ledger-company-grid";

  const worked = document.createElement("div");
  worked.className = "ledger-company-col ledger-company-col-good";
  worked.innerHTML = `<h3>Companies That Worked</h3>
    <p class="ledger-col-sub">The idea reached its goal before the safety line was hit.</p>`;
  worked.appendChild(_ledgerCompanyColumn("worked", ["WIN"], "No winners recorded yet. The list fills up as ideas are graded."));

  const failed = document.createElement("div");
  failed.className = "ledger-company-col ledger-company-col-bad";
  failed.innerHTML = `<h3>Companies That Did Not</h3>
    <p class="ledger-col-sub">The idea hit the safety line (a loss) or ran out of time and went nowhere.</p>`;
  failed.appendChild(_ledgerCompanyColumn("failed", ["LOSS", "TIMEOUT"], "No losers recorded yet. The list fills up as ideas are graded."));

  grid.append(worked, failed);
  host.appendChild(grid);

  const note = document.createElement("p");
  note.className = "ledger-note";
  note.innerHTML = `Ideas still running, or that expired without ever triggering, are left out of these two lists.
    "R" is one bite of risk - the gap between the buy price and the safety line.${_ledgerSight("r_multiple", "R")}`;
  host.appendChild(note);
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
      html += `<div class="fx-row" style="padding:8px 12px;">
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
      /* One hairline row per source: provider on the left, state chips on the
         right, last error (if any) as a wrapped sub-line. */
      const row = document.createElement("div");
      row.className = "fx-row";
      const name = document.createElement("span");
      name.className = "fx-k";
      name.textContent = source.provider;
      const status = document.createElement("span");
      const stateTone = source.state === "ok" || source.state === "healthy" ? "is-bull"
        : source.state === "error" || source.state === "failed" ? "is-bear" : "is-mut";
      status.className = "fx-v " + stateTone;
      const limitTone = source.rate_limit_ok ? "is-mut" : "is-neut";
      status.innerHTML = `<span>${source.state}</span>`
        + ` <span class="${limitTone}">${source.rate_limit_ok ? "rate ok" : "rate reached"}</span>`
        + ` <span class="is-mut">${source.calls}/${source.failures}</span>`;
      row.append(name, status);
      if (source.last_error) {
        const error = document.createElement("p");
        error.className = "fx-v is-bear";
        error.style.cssText = "flex:1 1 100%; white-space:normal; font-size:11px; text-align:right";
        error.textContent = source.last_error;
        row.appendChild(error);
        row.style.flexWrap = "wrap";
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
/* Pattern annotations ("HEAD_S", "BULL_INVERS", "ASCEND", "DOUBLE"...) pile up on
   a phone and hide the candles. They are off by default under 768px and the user
   can bring them back with the pill toggle above the chart. */
const FX_PATTERN_PREF = "nse.showPatterns";
const FX_MA_PREF = "nse.showMA";
const FX_EMA10_PREF = "nse.showEma10";
let _patternSignals = [];
let _patternsVisible = null;
let _maVisible = null;
let _maPanelOpen = false;

/* The average set. Owner asked for "10, 20, 50 ema/sma — whatever's important";
   this system's own evidence points at 20/50/200 (see justifyDefaultSet below).
   `def: true` lines are drawn on load; everything else is one click away. */
const MA_DEFS = [
  { key: "sma10", label: "SMA 10", short: "s10", kind: "sma", period: 10, color: "#22d3ee", width: 1, dashed: true, def: true },
  { key: "ema10", label: "EMA 10", short: "e10", kind: "ema", period: 10, color: "#60a5fa", width: 1, dashed: false, def: false },
  { key: "sma20", label: "SMA 20", short: "s20", kind: "sma", period: 20, color: "#f472b6", width: 1, dashed: true, def: false },
  { key: "ema20", label: "EMA 20", short: "e20", kind: "ema", period: 20, color: "#fbbf24", width: 2, dashed: false, def: true },
  { key: "ema50", label: "EMA 50", short: "e50", kind: "ema", period: 50, color: "#a78bfa", width: 2, dashed: false, def: true },
  { key: "ema200", label: "EMA 200", short: "e200", kind: "ema", period: 200, color: "#94a3b8", width: 2, dashed: false, def: true },
];
/* Why exactly these four are drawn on load:
   - SMA 10  : the owner's "10" as a simple mean — the immediate trend line, and
               the only SMA the terminal had (there was none before this pass).
   - EMA 20  : the system's short-term trend / pullback-zone reference
               (setup.py ema_proximity, meta features d10/d20).
   - EMA 50  : medium-term trend, used by the scanners and slope50.
   - EMA 200 : long-term trend filter used by every scan (above200, slope200,
               days_above_200_30); dropping it would hide the regime line.
   EMA 10 and SMA 20 stay available but OFF: EMA 10 duplicates SMA 10 almost
   exactly, and SMA 20 sits on top of EMA 20, so both add ink without adding
   information. Four drawn lines is the ceiling we hold. */
function _maSeriesByKey(key) {
  return { sma10, ema10, sma20, ema20, ema50, ema200 }[key] || null;
}

function _maVisibleMap() {
  if (_maVisible) return _maVisible;
  _maVisible = {};
  MA_DEFS.forEach((d) => { _maVisible[d.key] = d.def; });
  try {
    const raw = sessionStorage.getItem(FX_MA_PREF);
    if (raw) {
      const stored = JSON.parse(raw) || {};
      MA_DEFS.forEach((d) => {
        if (typeof stored[d.key] === "boolean") _maVisible[d.key] = stored[d.key];
      });
    } else {
      /* Carry over a choice made by the previous EMA-10-only toggle. */
      const legacy = sessionStorage.getItem(FX_EMA10_PREF);
      if (legacy === "1") _maVisible.ema10 = true;
      else if (legacy === "0") _maVisible.ema10 = false;
    }
  } catch (e) {}
  return _maVisible;
}

function _maWantVisible(key) { return !!_maVisibleMap()[key]; }

function _setMaVisible(key, value) {
  _maVisibleMap()[key] = !!value;
  try { sessionStorage.setItem(FX_MA_PREF, JSON.stringify(_maVisibleMap())); } catch (e) {}
  _applyMaVisibility();
}

/* Every average that has data AND is switched on. Legend, toolbar and readout
   all read from this one list, so they can never disagree with the pane. */
function _maDrawn() {
  return MA_DEFS.filter((d) => _maData[d.key] && _maWantVisible(d.key));
}

function _applyMaVisibility() {
  MA_DEFS.forEach((d) => {
    const s = _maSeriesByKey(d.key);
    if (s) s.applyOptions({ visible: _maWantVisible(d.key) });
  });
  _renderChartChrome();
  _paintReadout();
}

/* Simple moving average of the closes — first point at index period-1. */
function _sma(candles, period) {
  const out = [];
  if (!candles || candles.length < period) return out;
  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += Number(candles[i].close);
    if (i >= period) sum -= Number(candles[i - period].close);
    if (i >= period - 1) {
      out.push({ time: candles[i].time, value: Math.round((sum / period) * 100) / 100 });
    }
  }
  return out;
}

function _patternsWantVisible() {
  if (_patternsVisible !== null) return _patternsVisible;
  try {
    const stored = sessionStorage.getItem(FX_PATTERN_PREF);
    if (stored === "1") { _patternsVisible = true; return true; }
    if (stored === "0") { _patternsVisible = false; return false; }
  } catch (e) {}
  _patternsVisible = window.innerWidth >= 768;
  return _patternsVisible;
}

/* RSI-14 with Wilder smoothing, derived from the candle closes we already hold.
   /api/cockpit/{symbol}/chart returns no RSI key and terminal_api.py is owned by
   another writer this pass, so computing it client-side keeps the API contract
   untouched and still gives a real oscillator. */
function _rsi14(candles, period) {
  const p = period || 14;
  const out = [];
  if (!candles || candles.length <= p) return out;
  const close = (i) => Number(candles[i].close);
  let gain = 0, loss = 0;
  for (let i = 1; i <= p; i++) {
    const d = close(i) - close(i - 1);
    if (d >= 0) gain += d; else loss -= d;
  }
  let avgGain = gain / p, avgLoss = loss / p;
  const push = (i) => {
    let value;
    if (avgLoss === 0) value = 100;
    else if (avgGain === 0) value = 0;
    else value = 100 - 100 / (1 + avgGain / avgLoss);
    out.push({ time: candles[i].time, value: Math.round(value * 100) / 100 });
  };
  push(p);
  for (let i = p + 1; i < candles.length; i++) {
    const d = close(i) - close(i - 1);
    avgGain = (avgGain * (p - 1) + (d > 0 ? d : 0)) / p;
    avgLoss = (avgLoss * (p - 1) + (d < 0 ? -d : 0)) / p;
    push(i);
  }
  return out;
}

function _chartTheme() {
  return {
    layout: {
      background: { color: "transparent" }, textColor: "#a1a1aa",
      fontFamily: getComputedStyle(document.body).fontFamily, fontSize: 11,
    },
    grid: {
      vertLines: { color: "rgba(255,255,255,.04)" },
      horzLines: { color: "rgba(255,255,255,.04)" },
    },
  };
}

/* Two chart instances means two right price scales. If they differ in width the
   shared time axis drifts, so both are pinned to the same measured width. */
function _paneScaleWidth(c) {
  try {
    const ps = c && typeof c.priceScale === "function" ? c.priceScale("right") : null;
    return ps && typeof ps.width === "function" ? Number(ps.width()) || 0 : 0;
  } catch (e) { return 0; }
}

function _equalizePaneScales() {
  if (!chart || !rsiChart) return;
  const pw = _paneScaleWidth(chart), rw = _paneScaleWidth(rsiChart);
  const w = Math.max(76, pw, rw);
  try {
    if (pw && Math.abs(pw - w) > 1) chart.priceScale("right").applyOptions({ minimumWidth: w });
    if (rw && Math.abs(rw - w) > 1) rsiChart.priceScale("right").applyOptions({ minimumWidth: w });
  } catch (e) {}
}

function _resizePanes() {
  const fit = (el, c) => {
    if (!el || !c) return;
    const r = el.getBoundingClientRect();
    const w = Math.floor(r.width), h = Math.floor(r.height);
    if (w > 0 && h > 0) { try { c.resize(w, h); } catch (e) {} }
  };
  fit($("chartPrice"), chart);
  fit($("chartRsi"), rsiChart);
}

/* Panning or zooming either pane moves the other: one shared time axis. */
function _linkTimeScales(a, b) {
  if (!a || !b) return;
  const mirror = (src, dst) => src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (!range || _paneSync) return;
    _paneSync = true;
    try { dst.timeScale().setVisibleLogicalRange(range); } catch (e) {}
    _paneSync = false;
  });
  mirror(a, b);
  mirror(b, a);
}

function _bindCrosshairReadout() {
  const bind = (c) => {
    if (!c) return;
    c.subscribeCrosshairMove((param) => {
      if (!param || !param.time) { _paintReadout(); return; }
      const t = String(param.time);
      _paintReadout(_chartCandleByTime.get(t), t, _chartRsiByTime.get(t));
    });
  };
  bind(chart);
  bind(rsiChart);
}

/* One legible readout: OHLC + RSI value, plus the MAs that are actually drawn.
   Falls back to the latest stored bar when the pointer is off the chart. */
function _paintReadout(bar, time, rsi) {
  const el = $("chartReadout");
  if (!el) return;
  const b = bar || _chartLastBar;
  if (!b) { el.textContent = ""; return; }
  const t = time || b.time;
  const wide = window.innerWidth >= 768;
  const n2 = (v) => (v == null || !Number.isFinite(Number(v))) ? "—" : Number(v).toFixed(2);
  const rv = (rsi === undefined || rsi === null)
    ? (time ? _chartRsiByTime.get(t) : _chartLastRsi) : rsi;
  const ema = _chartEmaByTime.get(t) || {};
  const bits = [`<span class="ro-date">${t}</span>`];
  if (wide) {
    bits.push(`<span class="ro-k">O</span>${n2(b.open)} <span class="ro-k">H</span>${n2(b.high)} `
      + `<span class="ro-k">L</span>${n2(b.low)} <span class="ro-k">C</span>${n2(b.close)}`);
  } else {
    bits.push(`<span class="ro-k">C</span>${n2(b.close)}`);
  }
  bits.push(`<span class="ro-rsi">RSI ${rv == null ? "—" : Number(rv).toFixed(1)}</span>`);
  if (wide) {
    _maDrawn().forEach((d) => {
      bits.push(`<span class="ro-k">${d.short}</span>${n2(ema[d.key])}`);
    });
  }
  el.innerHTML = bits.join(" ");
}

/* Show the recent, readable window instead of cramming all ~420 bars into the
   pane; fitContent only when the stored history is already short. */
function _applyDefaultRange() {
  if (!chart) return;
  const n = _chartCandleByTime.size;
  if (!n) return;
  const target = window.innerWidth < 620 ? 60 : window.innerWidth < 950 ? 100 : 140;
  try {
    if (n > target + 8) chart.timeScale().setVisibleLogicalRange({ from: n - target, to: n + 3 });
    else chart.timeScale().fitContent();
  } catch (e) {}
}

function _setChartData(data) {
  const candles = (data && data.candles) || [];
  _chartCandleByTime = new Map(candles.map((c) => [String(c.time), c]));
  _chartLastBar = candles.length ? candles[candles.length - 1] : null;
  const maData = {
    sma10: _sma(candles, 10),
    sma20: _sma(candles, 20),
    ema10: data.ema10 || [],
    ema20: data.ema20 || [],
    ema50: data.ema50 || [],
    ema200: data.ema200 || [],
  };
  _maData = {};
  MA_DEFS.forEach((d) => { _maData[d.key] = !!(maData[d.key] && maData[d.key].length); });
  candleSeries.setData(candles);
  MA_DEFS.forEach((d) => {
    const s = _maSeriesByKey(d.key);
    if (s) s.setData(maData[d.key] || []);
  });
  _chartEmaByTime = new Map();
  MA_DEFS.forEach((d) => {
    (maData[d.key] || []).forEach((point) => {
      const t = String(point.time);
      const rec = _chartEmaByTime.get(t) || {};
      rec[d.key] = point.value;
      _chartEmaByTime.set(t, rec);
    });
  });
  _applyMaVisibility();
  const rsi = _rsi14(candles, 14);
  _chartRsiByTime = new Map(rsi.map((point) => [String(point.time), point.value]));
  _chartLastRsi = rsi.length ? rsi[rsi.length - 1].value : null;
  rsiReady = rsi.length > 0;
  rsiSeries.setData(rsi);
  /* The RSI line starts 14 bars late (Wilder warm-up). The band is therefore
     drawn on EVERY price bar's timestamp, so the RSI pane owns the same time
     axis as the price pane and logical-space pan/zoom mirroring lines up
     exactly instead of drifting by the warm-up offset. */
  rsiBand.setData(candles.map((c) => ({ time: c.time, value: 70 })));
  _renderChartChrome();
  _applyDefaultRange();
  requestAnimationFrame(() => {
    _resizePanes();
    _applyDefaultRange();
    _equalizePaneScales();
    _paintReadout();
  });
}

function _renderChartChrome() {
  const toolbar = $("chartToolbar");
  const n = _patternSignals.length;
  const on = _patternsWantVisible();
  const drawn = _maDrawn();
  const available = MA_DEFS.filter((d) => _maData[d.key]);
  if (toolbar) {
    toolbar.innerHTML = `
      <span class="fx-chip mono-sans" style="color:var(--fx-zinc-500)">
        <span class="fx-dot" style="background:var(--fx-bull)"></span>Price
        <span style="opacity:.5">/</span>${drawn.length} of ${available.length} averages
      </span>
      <button type="button" id="maPanelToggle" class="fx-toggle" aria-pressed="${_maPanelOpen ? "true" : "false"}"
        aria-expanded="${_maPanelOpen ? "true" : "false"}"
        title="Choose which averages are drawn on the price pane. SMA lines are dashed, EMA lines are solid.">
        <span>Averages</span>
        <span class="fx-chip-count">(${drawn.length} on)</span>
      </button>
      <button type="button" id="patternToggle" class="fx-toggle" aria-pressed="${on ? "true" : "false"}"
        data-icon="layers" data-icon-size="14"
        title="${n ? "Show or hide the algorithmic pattern annotations over the price lines" : "No stored pattern annotations for this symbol yet"}">
        <span>${on ? "Hide" : "Show"} Patterns</span>
        <span class="fx-chip-count">(${n})</span>
      </button>
      <div id="maPanel" class="fx-ma-panel"${_maPanelOpen ? "" : " hidden"}>
        ${available.map((d) => {
          const vis = _maWantVisible(d.key);
          return `<button type="button" class="fx-ma-chip${vis ? " is-on" : ""}" data-ma="${d.key}"
            aria-pressed="${vis ? "true" : "false"}"
            title="${d.label}: ${d.kind === "sma" ? "simple" : "exponential"} ${d.period}-period average of the close, drawn ${d.dashed ? "dashed" : "solid"}. Click to ${vis ? "hide" : "show"} it.">
            <span class="fx-ma-dot" style="background:${d.color}"></span>${d.label}
            <span class="fx-ma-state">${vis ? "on" : "off"}</span>
          </button>`;
        }).join("")}
      </div>`;
    const panelBtn = $("maPanelToggle");
    if (panelBtn) {
      panelBtn.addEventListener("click", () => {
        _maPanelOpen = !_maPanelOpen;
        _renderChartChrome();
      });
    }
    toolbar.querySelectorAll(".fx-ma-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const key = chip.dataset.ma;
        _setMaVisible(key, !_maWantVisible(key));
      });
    });
    const btn = $("patternToggle");
    if (btn) {
      btn.addEventListener("click", () => {
        _patternsVisible = !_patternsWantVisible();
        try { sessionStorage.setItem(FX_PATTERN_PREF, _patternsVisible ? "1" : "0"); } catch (e) {}
        _applyMarkersToSeries();
        _renderChartChrome();
      });
    }
  }
  const legend = $("chartLegend");
  if (legend) {
    legend.hidden = !candleSeries;
    /* Every average that exists gets an entry, and its state is explicit: drawn
       = full-strength swatch, switched off = dimmed swatch + "off". An off line
       can never look drawn. */
    const items = ['<span class="lg-item"><span class="lg-swatch c-candle"></span>Price</span>'];
    MA_DEFS.forEach((d) => {
      if (!_maData[d.key]) return;
      const vis = _maWantVisible(d.key);
      items.push(`<span class="lg-item${vis ? "" : " is-off"}">`
        + `<span class="lg-swatch c-${d.key}"></span>${d.label}`
        + `${vis ? "" : ' <span class="lg-off">off</span>'}</span>`);
    });
    if (rsiReady) {
      items.push('<span class="lg-item"><span class="lg-swatch c-rsi"></span>RSI 14 '
        + '<span class="lg-off">30/70</span></span>');
    }
    legend.innerHTML = items.join("");
  }
  const note = $("chartMobileNote");
  if (note) {
    note.textContent = on
      ? "Pattern annotations are on. Turn them off to read the price lines cleanly."
      : "Pattern annotations are hidden on narrow screens so the price line stays readable.";
  }
}

/** Draw (or clear) the stored pattern annotations according to the toggle. */
function _applyMarkersToSeries() {
  if (!candleSeries) return;
  const visible = _patternsWantVisible();
  const wrap = document.querySelector(".fx-chart-wrap");
  if (wrap) wrap.classList.toggle("is-patterns-hidden", !visible);
  if (!visible || !_patternSignals.length) {
    candleSeries.setMarkers([]);
    return;
  }
  /* Text labels are the biggest offenders at phone width; keep the markers,
     drop the words. Labels are also suppressed on the last few bars: there the
     text is painted into the price-scale gutter and comes out clipped (signals
     whose date is newer than the last stored bar all stack on that bar). */
  const showText = window.innerWidth >= 768;
  const _times = [..._chartCandleByTime.keys()];
  const _liveEdge = _times.length ? _times[Math.max(0, _times.length - 8)] : "";
  const markers = _patternSignals.map((s) => {
    const d = String(s.date).slice(0, 10);
    let color = "#fbbf24";
    let position = "aboveBar";
    let shape = "circle";
    const text = (showText && s.pattern && !(d >= _liveEdge)) ? s.pattern.slice(0, 6) : "";
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
}

function resetChart() {
  const priceEl = $("chartPrice");
  const rsiEl = $("chartRsi");
  if (!priceEl || !rsiEl) return;
  if (chart) { try { chart.remove(); } catch (e) {} }
  if (rsiChart) { try { rsiChart.remove(); } catch (e) {} }
  chart = null; candleSeries = null;
  sma10 = ema10 = sma20 = ema20 = ema50 = ema200 = null;
  rsiChart = null; rsiSeries = null; rsiBand = null; rsiReady = false;
  priceEl.innerHTML = "";
  rsiEl.innerHTML = "";
  const theme = _chartTheme();
  const crosshair = {
    mode: LightweightCharts.CrosshairMode.Normal,
    vertLine: { color: "rgba(255,255,255,.3)", width: 1, style: LightweightCharts.LineStyle.Dashed, labelVisible: true },
    horzLine: { color: "rgba(255,255,255,.3)", width: 1, style: LightweightCharts.LineStyle.Dashed, labelVisible: true },
  };
  const scale = { borderColor: "rgba(255,255,255,.08)", minimumWidth: 76 };
  const scroll = { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false };

  /* Price pane: no time axis of its own — the RSI pane below carries the shared
     dates, which is the two-pane TradingView / Angel-One arrangement. */
  chart = LightweightCharts.createChart(priceEl, Object.assign({}, theme, {
    autoSize: true,
    rightPriceScale: Object.assign({ scaleMargins: { top: 0.14, bottom: 0.14 } }, scale),
    timeScale: {
      visible: false, borderColor: "rgba(255,255,255,.08)",
      rightOffset: 4, barSpacing: 6, fixLeftEdge: true, fixRightEdge: true,
    },
    crosshair,
    handleScroll: scroll,
  }));
  candleSeries = chart.addCandlestickSeries({ upColor: "#34d399", downColor: "#fb7185", borderVisible: false, wickUpColor: "#34d399", wickDownColor: "#fb7185" });
  /* One line series per entry in MA_DEFS. SMA lines are dashed and EMA lines are
     solid, so the family is readable even before the legend is consulted. */
  MA_DEFS.forEach((d) => {
    const line = chart.addLineSeries({
      color: d.color,
      lineWidth: d.width,
      lineStyle: d.dashed ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
      visible: _maWantVisible(d.key),
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    if (d.key === "sma10") sma10 = line;
    else if (d.key === "sma20") sma20 = line;
    else if (d.key === "ema10") ema10 = line;
    else if (d.key === "ema20") ema20 = line;
    else if (d.key === "ema50") ema50 = line;
    else if (d.key === "ema200") ema200 = line;
  });

  /* RSI pane: own 0-100 scale, shaded 30-70 band, dashed 30/70 levels. */
  rsiChart = LightweightCharts.createChart(rsiEl, Object.assign({}, theme, {
    autoSize: true,
    rightPriceScale: Object.assign({ scaleMargins: { top: 0.12, bottom: 0.12 } }, scale),
    timeScale: {
      visible: true, borderColor: "rgba(255,255,255,.08)",
      rightOffset: 4, barSpacing: 6, fixLeftEdge: true, fixRightEdge: true,
    },
    crosshair,
    handleScroll: scroll,
  }));
  rsiBand = rsiChart.addBaselineSeries({
    baseValue: { type: "price", price: 30 },
    topFillColor1: "rgba(96,165,250,.17)",
    topFillColor2: "rgba(96,165,250,.05)",
    bottomFillColor1: "rgba(0,0,0,0)",
    bottomFillColor2: "rgba(0,0,0,0)",
    topLineColor: "rgba(0,0,0,0)",
    bottomLineColor: "rgba(0,0,0,0)",
    lineWidth: 1, lineVisible: false,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  });
  rsiSeries = rsiChart.addLineSeries({ color: "#c084fc", lineWidth: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: true, crosshairMarkerRadius: 3 });
  rsiSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
  rsiLevelLines = [
    rsiSeries.createPriceLine({ price: 70, color: "rgba(251,113,133,.75)", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "" }),
    rsiSeries.createPriceLine({ price: 30, color: "rgba(52,211,153,.75)", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "" }),
  ];

  _linkTimeScales(chart, rsiChart);
  _bindCrosshairReadout();
  _renderChartChrome();
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
  requestAnimationFrame(() => { _resizePanes(); _equalizePaneScales(); _paintReadout(); });
}

async function _applyPatternMarkers(symbol) {
  if (!candleSeries) return;
  try {
    const h = await api(`/api/patterns/history/${symbol}?limit=500`);
    _patternSignals = (h && h.signals) || [];
  } catch (e) {
    _patternSignals = [];
  }
  _applyMarkersToSeries();
  _renderChartChrome();
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
  _setChartData(chartData);
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
        <div class="fx-row"><span>Trigger</span><strong>${setup.trigger}</strong></div>
        <div class="fx-row"><span>PDL Stop</span><strong>${setup.stop}</strong></div>
        <div class="fx-row"><span>Target (3R)</span><strong>${setup.target}</strong></div>
        <button class="toggle-btn" data-target="setupDetails">Show setup details</button>
        <div id="setupDetails" class="details-panel hidden">
          <div class="fx-row"><span data-explain="pullback" title="Click to learn what this is">The pause dip</span><strong>${(setup.pullback * 100).toFixed(1)}%</strong></div>
          <div class="fx-row"><span data-explain="impulse" title="Click to learn what this is">The earlier rise</span><strong>${(setup.impulse * 100).toFixed(1)}%</strong></div>
          <div class="fx-row"><span>Resting on average price</span><strong>${setup.zone}</strong></div>
          <div class="fx-row"><span data-explain="shape_score" title="Click to learn what this is">How tidy the pause is</span><strong>${setup.shape ?? "—"}/100</strong></div>
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
        <div class="fx-row"><span>Symbol</span><strong>${symbol}</strong></div>
        <div class="fx-row"><span>Status</span><strong>${summary.status || "—"}</strong></div>
        <div class="fx-row"><span>Fund Score</span><strong>${fmt(summary.fund_score)}</strong></div>
        <div class="fx-row"><span>Mcap</span><strong>₹${fmt(summary.mcap_cr)} cr</strong></div>`;
    }
    try {
      const sz = await api(`/api/sizing/${symbol}`);
      renderSizing(sz);
    } catch (e) {}
  }
  try {
    const meta = (await api(`/api/meta/${symbol}`)) || {};
    if (setupSummary) {
      /* Feature names are internal codes (atr, vc, slope200...). Nobody outside
         the model should have to read them, so each gets a plain gloss. */
      const FEATURE_PLAIN = {
        atr: "How jumpy the price normally is",
        vc: "How tight the recent trading range is",
        slope200: "Whether the long-term trend is sloping up",
        slope50: "Whether the medium-term trend is sloping up",
        d10: "Distance from the short-term average price",
        d20: "Distance from the medium-term average price",
        d52: "Distance from the 52-week high",
        mom1: "Move over the last month",
        mom3: "Move over the last three months",
        mom6: "Move over the last six months",
        above200: "Trading above its long-term average",
        pb: "Price compared with the company's books",
        rv: "Recent price swings versus normal",
        vcr: "How much trading volume has dried up",
        ret_std20: "How steady the last month of moves has been",
        below52: "How far below the 52-week high it sits",
        pat_htf: "A tight flag pattern was found",
        pat_tri: "A triangle pattern was found",
        pat_db: "A double-bottom pattern was found",
        pat_ihs: "An inverse head-and-shoulders was found",
        pat_bear: "A topping warning was found",
        pat_any: "Any recognised pattern was found",
        dtw_sim: "How closely it resembles past winners",
        delivery_sim: "How much stock buyers kept overnight",
        days_above_200_30: "How many recent days it held above its long-term average",
        days_above_50_30: "How many recent days it held above its medium-term average",
        ema200_dist_z: "How far it has stretched from its long-term average",
      };
      const why = (meta.why || []).map(w => {
        const plain = FEATURE_PLAIN[w.feature] || w.feature.replace(/_/g, " ");
        return `<div class="fx-row"><span class="fx-k" title="Internal feature name: ${w.feature}">${plain}</span>`
          + `<span class="fx-v ${w.impact > 0 ? "is-bull" : "is-bear"}">${w.impact > 0 ? "+" : ""}${w.impact}</span></div>`;
      }).join("");
      /* The score row is the whole card: label + target chip + the figure. No
         prose in the layout — the help text lives behind the (?) and inside the
         collapsible methodology block below. The row renders even when no score
         is stored, so the layout is never silently missing: it says so instead. */
      const hasScore = meta.p_win != null && Number.isFinite(Number(meta.p_win));
      const pct = hasScore ? Math.round(Number(meta.p_win) * 100) : null;
      const tone = !hasScore ? "is-none" : pct >= 50 ? "is-bull" : pct >= 35 ? "is-neut" : "is-bear";
      const target = meta.target_pct != null && Number.isFinite(Number(meta.target_pct))
        ? Math.round(Number(meta.target_pct) * 100)
        : 50;
      const targetChip = `<span class="fx-score-target">Target &gt;${target}%</span>`;
      const scoreValue = hasScore ? `${pct}%` : "—";
      const scoreNote = hasScore ? "" : `<span class="fx-score-note">no score stored</span>`;
      const whyBlock = why
        ? `<details class="fx-method"><summary>
             <svg class="fx-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" aria-hidden="true"><path d="M4 19V5M4 19h16"/><path d="m8 15 3.5-4 3 3L20 7"/></svg>
             What pushed this score up or down
             <svg class="fx-icon-sm fx-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
           </summary>
           <div class="fx-method-body">
             <p>Each line is one thing the model looked at, and how much it pushed today's score up (+) or down (&minus;). A plus does not mean the company is good &mdash; only that this model weighed it that way.</p>
             ${why}
           </div>
         </details>`
        : "";
      setupSummary.insertAdjacentHTML("beforeend", `
        <div class="model-explainer">
          <div class="fx-score-row ${tone}">
            <span class="fx-score-label">
              <span data-explain="p_win" data-explain-stop title="${window.MODEL_EVENT_SCORE_HELP}">Model Event Score</span>
              <button type="button" class="fx-help" data-explain="p_win"
                aria-label="What is the model event score?">?</button>
            </span>
            ${scoreNote}
            ${targetChip}
            <span class="fx-score-value">${scoreValue}</span>
          </div>
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
  const pctText = value => value == null || !Number.isFinite(value)
    ? "insufficient bars" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
  const pctTone = value => value == null || !Number.isFinite(value)
    ? "is-mut" : value > 0 ? "is-bull" : value < 0 ? "is-bear" : "is-mut";
  /* Clean key/value rows — no boxes, no disabled-input look. */
  const latestLine = (label, value, cls) => `
    <div class="fx-row"><span class="fx-k">${label}</span>
      <span class="fx-v ${cls || ""}">${value}</span></div>`;
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
      `${close >= Number(value) ? "above" : "below"} ${name}`).join(" / ")
    : "EMA context unavailable";
  const trendTone = available.length && available.every(([, v]) => close >= Number(v))
    ? "is-bull" : "is-mut";
  box.innerHTML = `
    <div class="fx-row">
      <span class="fx-k">Latest stored close <span class="fx-label">${last.time}</span></span>
      <span class="fx-v is-lead">₹${close.toFixed(2)}</span>
    </div>
    ${latestLine("1-session change", pctText(daily), pctTone(daily))}
    ${latestLine("20-session change", pctText(change(20)), pctTone(change(20)))}
    ${latestLine("60-session change", pctText(change(60)), pctTone(change(60)))}
    ${latestLine("Trend context", trend, `${trendTone} is-long`)}
    <details class="fx-method">
      <summary>
        <svg class="fx-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></svg>
        Methodology &amp; source
        <svg class="fx-icon-sm fx-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
      </summary>
      <div class="fx-method-body">
        <p>Daily end-of-day data only. This describes recent price behaviour; it does not predict the next move.</p>
        <p>Source bar date: <span class="fx-fig">${last.time}</span>. Changes are measured close-to-close against the stored bars, not against an intraday feed.</p>
      </div>
    </details>`;
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
    compact = `<div class="fx-row"><span>Sizing</span><strong>unavailable yet</strong></div>`;
    details = capitalEditor(sz.capital);
  } else if (sz.shares !== undefined) {
    const allocatedPct = sz.actual_alloc_pct ?? sz.alloc_pct;
    const plannedRiskPct = sz.actual_planned_risk_pct ?? sz.risk_pct;
    compact = `<div class="fx-row"><span>Research position size</span><strong>${moneyFmt(sz.suggested_value)} (${fmt(allocatedPct, "%")})</strong></div>
      <div class="fx-row"><span>Quantity at trigger</span><strong>${sz.shares} shares${sz.actionable === false ? " (not actionable)" : ""}</strong></div>`;
    details = `
      <div class="fx-row"><span>Capital</span><strong>${moneyFmt(sz.capital)}</strong></div>
      <div class="fx-row"><span>Planned stop-risk budget</span><strong>${fmt(sz.planned_risk_budget_pct ?? sz.risk_per_trade_pct, "%")}</strong></div>
      <div class="fx-row"><span>Regime adjustment</span><strong>${sz.regime_level || "—"} · ×${fmt(sz.regime_mult)}</strong></div>
      <div class="fx-row"><span>Shape adjustment</span><strong>${fmt(sz.shape_score)} / 100 · ×${fmt(sz.quality_mult)}</strong></div>
      <div class="fx-row"><span>Planned loss at stop</span><strong>${moneyFmt(sz.risk_amount)} (${fmt(plannedRiskPct, "%")})</strong></div>
      <div class="fx-row"><span>Limiting rule</span><strong>${sz.binding_cap || "—"}</strong></div>
      <p class="method-note">${sz.risk_note || "Fixed-risk research sizing. No calibrated trade win probability or Kelly input is used. Quantity is limited by planned stop risk and maximum allocation; gaps, slippage, fees, and taxes can increase losses."}</p>
      ${sz.reason ? `<p class="method-warning">${sz.reason}</p>` : ""}`;
  } else {
    compact = `<div class="fx-row"><span>Suggested allocation</span><strong>${fmt(sz.alloc_pct, "%")} of capital</strong></div>`;
    details = `
      <div class="fx-row"><span>Capital</span><strong>${moneyFmt(sz.capital)}</strong></div>
      <div class="fx-row"><span>Planned stop-risk budget</span><strong>${fmt(sz.planned_risk_budget_pct ?? sz.risk_per_trade_pct, "%")}</strong></div>
      <div class="fx-row"><span>Regime adjustment</span><strong>${sz.regime_level || "—"} · ×${fmt(sz.regime_mult)}</strong></div>
      <div class="fx-row"><span>Shape adjustment</span><strong>${fmt(sz.shape_score)} / 100 · ×${fmt(sz.quality_mult)}</strong></div>
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
  return `<div class="fx-row"><span>Set capital</span><strong style="display:flex;gap:6px;">
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
        <div class="fx-row"><span>Conviction score</span><strong>${dv.score != null ? (dv.score * 100).toFixed(0) + "/100" : "—"}</strong></div>
        <button class="toggle-btn" data-target="deliveryDetails">Show raw delivery data</button>
        <div id="deliveryDetails" class="details-panel hidden">
          <div class="fx-row"><span>Latest (${last ? last.date : "—"})</span><strong>${last ? last.delivery_pct + "%" : "—"}</strong></div>
          <div class="fx-row"><span>Traded / Deliverable</span><strong>${last ? (last.traded_qty / 100000).toFixed(1) + "L / " + (last.deliverable_qty / 100000).toFixed(1) + "L" : "—"}</strong></div>
        </div>`;
    } else {
      box.innerHTML = `<h3 style="margin:0;font-size:15px;">📦 Delivery %</h3>
        <div class="fx-row"><span>Status</span><strong>no data yet</strong></div>`;
    }
  } catch (e) {
    box.innerHTML = `<h3 style="margin:0;font-size:15px;">📦 Delivery %</h3>
      <div class="fx-row"><span>Status</span><strong>endpoint unavailable</strong></div>`;
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
  const btnLabel = button ? button.querySelector(".fx-open-label") : null;
  if (button) button.disabled = true;
  if (btnLabel) btnLabel.textContent = "Refreshing…";
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
    if (button) button.disabled = false;
    if (btnLabel) btnLabel.textContent = "Refresh";
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
  _wireMobileNav();
  hydrateTips(document);
  window.addEventListener("resize", _onViewportChange);
  _restoreNavigation(true);
  refreshAll(true);
});

/** Long-form panel prose lives in data-tip and is surfaced on hover/focus, so it
 *  never pushes indicators below the fold. */
function hydrateTips(root) {
  (root || document).querySelectorAll("[data-tip]").forEach((el) => {
    if (!el.getAttribute("title")) el.setAttribute("title", el.dataset.tip);
  });
}
window.hydrateTips = hydrateTips;

/* ---------------------------------------------------------------------------
   Mobile navigation drawer: the sidebar becomes an off-canvas sheet under
   950px and is opened by the hamburger. It closes on navigation, on Escape,
   and when the scrim is tapped. Desktop keeps the sticky sidebar.
   ------------------------------------------------------------------------- */
function _wireMobileNav() {
  const toggle = $("panelNavToggle");
  const close = () => { if (toggle) toggle.checked = false; };
  document.querySelectorAll("[data-close-nav]").forEach((el) => {
    el.addEventListener("click", close);
  });
  document.querySelectorAll("#panelNav .nav-btn, #navRail .nav-btn").forEach((btn) => {
    btn.addEventListener("click", close);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toggle && toggle.checked) close();
  });
}

/* Pattern labels are only drawn from 768px up; keep that in sync on resize. */
let _resizeTimer = null;
function _onViewportChange() {
  if (_resizeTimer) clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(() => {
    _applyMarkersToSeries();
    _resizePanes();
    _equalizePaneScales();
    _renderChartChrome();
    _paintReadout();
  }, 160);
}
