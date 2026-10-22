// Playbook — book-exact rules, per-stock tags, one-click matches, backtest.
//
// The server owns every rule. This file only:
//   1. renders the strategy catalogue (formula, params, exits, stats),
//   2. asks /api/playbook/signals for one strategy (or one symbol),
//   3. shows the exact exits attached to the selected tag,
//   4. starts the scan/backtest jobs and polls their status.
//
// A blank day is a valid answer. Nothing here invents a match to fill a table.

const PB = window.PB = {
  data: null,
  filter: null,
  signals: [],
  selected: null,
  scanTimer: null,
  btTimer: null,
  loading: false,
};

const pbEsc = (v) => String(v == null ? "" : v)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

function pbN(v, dp = 0) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-IN", {
    minimumFractionDigits: dp, maximumFractionDigits: dp,
  });
}

function pbPct(v, dp = 1) {
  if (v === null || v === undefined || v === "") return "-";
  const n = Number(v);
  return Number.isFinite(n) ? `${(n * 100).toFixed(dp)}%` : "-";
}

function pbR(v) {
  if (v === null || v === undefined || v === "") return "-";
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}R`;
}

function pbTone(v) {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "pb-pos" : "pb-neg";
}

function pbMeta(sid) {
  const list = (PB.data && PB.data.strategies) || [];
  return list.find((s) => s.id === sid) || {
    id: sid, name: sid, short: sid, book: "", params: {}, exit_text: {},
  };
}

function pbKey(r) {
  return `${r.strategy}|${r.symbol}|${r.direction}`;
}

function pbTruncate(text, n) {
  const s = String(text == null ? "" : text);
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

// ---------------------------------------------------------------- status ---
function pbSetStatus(id, text, tone) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("pb-warn", tone === "warn");
}

function pbScanLabel(scan) {
  if (!scan) return "No scan yet.";
  if (scan.running) {
    return scan.message || `Scanning ${scan.scanned || 0}/${scan.total || "?"}…`;
  }
  if (scan.status === "idle") return "No scan yet.";
  const date = scan.as_of && !String(scan.message || "").includes(scan.as_of)
    ? ` · ${scan.as_of}` : "";
  return `${scan.message || scan.status}${date}`;
}

function pbBtLabel(bt) {
  if (!bt) return "No backtest yet.";
  if (bt.running) return bt.message || `Backtesting ${bt.done || 0}/${bt.total || "?"}…`;
  if (bt.status === "idle") return "No backtest yet.";
  const when = bt.finished_at ? ` · ${bt.finished_at}` : "";
  return `${bt.message || bt.status}${when}`;
}

function pbRenderJobStatus(data) {
  const scan = data.scan || {};
  const bt = data.backtest || {};
  // The in-memory job state is lost on API restart. The rows are not: the
  // scan date and the newest backtest run_at are persisted, so show those
  // instead of claiming nothing has ever run.
  let scanText = pbScanLabel(scan);
  if (!scan.running && scan.status === "idle" && data.as_of) {
    const tags = (data.strategies || [])
      .reduce((n, s) => n + Number(s.total_tags != null
        ? s.total_tags : Number(s.matches || 0) + Number(s.warnings || 0)), 0);
    scanText = `Latest saved scan: ${data.as_of} · ${tags} tag${tags === 1 ? "" : "s"}`;
  }
  let btText = pbBtLabel(bt);
  if (!bt.running && bt.status === "idle") {
    const runs = (data.strategies || [])
      .map((s) => s.backtest && s.backtest.run_at)
      .filter(Boolean).sort();
    if (runs.length) {
      const latest = runs[runs.length - 1];
      const count = (data.strategies || []).filter((s) => s.backtest).length;
      btText = `Latest saved backtest: ${latest} · ${count} rule${count === 1 ? "" : "s"}`;
    }
  }
  pbSetStatus("pbScanStatus", scanText, scan.running ? "warn" : "");
  pbSetStatus("pbBacktestStatus", btText, bt.running ? "warn" : "");
  const scanBtn = document.getElementById("pbScanBtn");
  const btBtn = document.getElementById("pbBacktestBtn");
  if (scanBtn) scanBtn.disabled = !!scan.running;
  if (btBtn) btBtn.disabled = !!bt.running;
  if (scan.running) pbPollScan();
  if (bt.running) pbPollBacktest();
}

// ------------------------------------------------------------- catalogue ---
function pbExitTextHtml(exits) {
  const keys = ["stop", "target", "offset", "invalidation", "exhaustion"];
  const rows = keys
    .filter((k) => exits && exits[k])
    .map((k) => `<dt>${pbEsc(k)}</dt><dd>${pbEsc(exits[k])}</dd>`)
    .join("");
  return rows ? `<dl class="pb-exit" style="margin-top:10px">${rows}</dl>` : "";
}

function pbCard(s) {
  const live = s.status === "live";
  const pending = s.status === "data_pending";
  const bt = s.backtest;
  const canBacktest = s.backtestable !== false;
  const matches = Number(s.matches || 0);
  const warnings = Number(s.warnings || 0);
  const smallN = !!bt && Number(bt.signals) > 0 && Number(bt.signals) < 20;
  const badge = live
    ? `<span class="pb-chip is-live">LIVE</span>`
    : `<span class="pb-chip is-warn">DATA PENDING</span>`;
  const stats = [
    ["Tags today", matches],
    ["Trades tested", bt ? pbN(bt.signals) : "—"],
    ["Expectancy", bt && bt.expectancy_r != null
      ? `${pbR(bt.expectancy_r)}${smallN ? "*" : ""}` : "—"],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd class="${k === "Expectancy" ? pbTone(bt && bt.expectancy_r) : ""}">${v}</dd></div>`)
    .join("");

  const pendingNote = pending
    ? `<p class="pb-formula" style="color:var(--fx-neut)">Needs: ${pbEsc(s.data_need || "data not stored yet")}. No match is fabricated.</p>`
    : "";
  const warnNote = warnings
    ? `<p class="pb-formula" style="color:var(--fx-neut)">${warnings} warning tag${warnings === 1 ? "" : "s"} (death cross) — shown separately, never counted as a long.</p>`
    : "";
  const btNote = live && !canBacktest
    ? `<p class="pb-formula">Scan only: ${pbEsc(s.backtest_note || "portfolio-level rule")}</p>`
    : "";

  return `<article class="pb-card${pending ? " is-pending" : ""}" data-strategy="${pbEsc(s.id)}">
    <header>
      <div>
        <span class="pb-code">${pbEsc(s.short || s.id)}</span>
        <h3>${pbEsc(s.name)}</h3>
        <p class="pb-book">${pbEsc(s.book)}</p>
      </div>
      ${badge}
    </header>
    <p class="pb-formula">${pbEsc(s.formula)}</p>
    <div class="pb-chips">
      <span class="pb-chip">${pbEsc(s.family)}</span>
      <span class="pb-chip">${pbEsc(s.direction)}</span>
      <span class="pb-chip">hold ${pbN(s.hold)} bars</span>
      <span class="pb-chip" title="Book prior, before any test">book ${pbPct(s.prior_win, 0)} / ${pbN(s.prior_payoff, 1)}R</span>
    </div>
    <dl class="pb-stats">${stats}</dl>
    ${pendingNote}${warnNote}${btNote}
    <footer>
      <button class="fx-btn fx-btn-xs" type="button" data-pb-show="${pbEsc(s.id)}"
        ${live ? "" : "disabled"}>Show matches</button>
      <button class="fx-btn fx-btn-ghost fx-btn-xs" type="button"
        data-pb-rule="${pbEsc(s.id)}">Rule &amp; exits</button>
    </footer>
    <div class="pb-rule-detail" id="pbRule-${pbEsc(s.id)}" hidden>
      <strong>Exact parameters</strong>
      <pre>${pbEsc(JSON.stringify(s.params || {}, null, 2))}</pre>
      ${pbExitTextHtml(s.exit_text || {})}
      <p style="margin:8px 0 0">${pbEsc(s.formula)}</p>
    </div>
  </article>`;
}

function pbRenderCatalogue(strategies) {
  const grid = document.getElementById("pbStrategyGrid");
  if (!grid) return;
  grid.innerHTML = strategies.length
    ? strategies.map(pbCard).join("")
    : `<p class="pb-empty">The rule catalogue is empty.</p>`;
}

function pbRenderBacktests(strategies) {
  const body = document.getElementById("pbBacktestsBody");
  const count = document.getElementById("pbBacktestCount");
  if (!body) return;
  const live = strategies.filter((s) => s.status === "live");
  const tested = strategies.filter((s) => s.backtest).length;
  const scanOnly = live.filter((s) => s.backtestable === false).length;
  const dataPending = strategies.filter((s) => s.status === "data_pending").length;
  if (count) {
    count.textContent = `${tested} backtested`
      + (scanOnly ? ` · ${scanOnly} scan-only` : "")
      + (dataPending ? ` · ${dataPending} data pending` : "");
  }
  body.innerHTML = strategies.map((s) => {
    const bt = s.backtest;
    const smallN = !!bt && Number(bt.signals) > 0 && Number(bt.signals) < 20;
    const window = bt
      ? `${pbN(bt.years, 0)}y · ${pbN(bt.universe_n)} cos · step ${pbN(bt.step_bars)}${smallN ? " · small n" : ""}`
      : (s.status === "data_pending"
          ? "data pending"
          : (s.backtestable === false ? "scan only" : ""));
    return `<tr>
      <td><strong>${pbEsc(s.short || s.id)}</strong><br><span style="color:var(--muted);font-size:10.5px">${pbEsc(s.name)}</span>${window ? `<br><span style="color:var(--muted);font-size:10px">${pbEsc(window)}</span>` : ""}</td>
      <td class="pb-num" title="${bt ? `avg win ${pbR(bt.avg_win_r)} · avg loss ${pbR(bt.avg_loss_r)}` : ""}">${bt ? pbN(bt.signals) : "—"}</td>
      <td class="pb-num">${bt && bt.win_rate != null ? pbPct(bt.win_rate) : "—"}</td>
      <td class="pb-num ${bt ? pbTone(bt.expectancy_r) : ""}">${bt && bt.expectancy_r != null ? `${pbR(bt.expectancy_r)}${smallN ? "*" : ""}` : "—"}</td>
      <td class="pb-num">${bt && bt.profit_factor != null ? pbN(bt.profit_factor, 2) : "—"}</td>
      <td class="pb-num">${bt ? `${pbN(bt.max_dd_r, 1)}R` : "—"}</td>
      <td class="pb-num">${bt && bt.median_hold != null ? `${pbN(bt.median_hold)} b` : "—"}</td>
    </tr>`;
  }).join("");
}

// ---------------------------------------------------------------- signals ---
function pbRenderSignals(rows, title, note) {
  const body = document.getElementById("pbSignalsBody");
  const titleEl = document.getElementById("pbResultsTitle");
  const noteEl = document.getElementById("pbResultsNote");
  const countEl = document.getElementById("pbResultsCount");
  if (!body) return;
  PB.signals = rows || [];
  if (titleEl) titleEl.textContent = title || "Latest tags";
  if (noteEl) noteEl.textContent = note || "Every match on the latest scan date.";
  if (countEl) {
    const warns = PB.signals.filter((r) => r.direction === "TOP_WARNING").length;
    const entries = PB.signals.length - warns;
    countEl.textContent = warns
      ? `${entries} entr${entries === 1 ? "y" : "ies"} · ${warns} warning${warns === 1 ? "" : "s"}`
      : `${entries} tag${entries === 1 ? "" : "s"}`;
  }
  if (!PB.signals.length) {
    body.innerHTML = `<tr><td colspan="9" class="pb-empty">No rule matched. A blank day is a valid answer — the scan does not invent a tag.</td></tr>`;
    return;
  }
  body.innerHTML = PB.signals.map((r) => {
    const m = pbMeta(r.strategy);
    const warning = r.direction === "TOP_WARNING";
    return `<tr class="pb-row" data-key="${pbEsc(pbKey(r))}">
      <td><strong>${pbEsc(r.symbol)}</strong></td>
      <td title="${pbEsc(m.book)}">${warning ? '<span class="pb-dir-warn" title="Distribution warning, not a buy">W</span> ' : ""}${pbEsc(m.short || m.name)}</td>
      <td class="pb-num">${pbN(r.entry, 2)}</td>
      <td class="pb-num">${pbN(r.stop, 2)}</td>
      <td class="pb-num">${pbN(r.target, 2)}</td>
      <td class="pb-num">${r.rr != null ? pbN(r.rr, 2) : "—"}</td>
      <td class="pb-num">${pbPct(r.risk_pct)}</td>
      <td>${pbEsc(r.confidence || "—")}</td>
      <td><span class="pb-why" title="${pbEsc(r.notes)}">${pbEsc(pbTruncate(r.notes, 120))}</span></td>
    </tr>`;
  }).join("");
}

function pbShowDetail(row) {
  const panel = document.getElementById("pbDetailPanel");
  if (!panel) return;
  PB.selected = row;
  document.querySelectorAll("#pbSignalsBody tr").forEach((tr) => {
    tr.classList.toggle("is-selected", tr.dataset.key === pbKey(row));
  });
  const m = pbMeta(row.strategy);
  document.getElementById("pbDetailTitle").textContent =
    `${row.symbol} · ${m.name}`;
  document.getElementById("pbDetailSubtitle").textContent =
    `${row.as_of} · ${m.book || "Playbook"} · identification only, not an order`;
  const warning = row.direction === "TOP_WARNING";
  const exits = row.exits || {};
  const warningLabels = warning
    ? { stop_out: "Warning invalidated", target: "Downside objective" } : {};
  const exitRows = ["stop_out", "target", "offset", "invalidation",
    "exhaustion", "time_exit"]
    .filter((k) => exits[k])
    .map((k) => {
      const e = exits[k] || {};
      const cond = e.condition ? ` — ${e.condition}` : "";
      // The condition already carries the price, so do not repeat it.
      const hard = e.hard_number != null && !e.condition
        ? ` (₹${pbN(e.hard_number, 2)})` : "";
      const sessions = e.sessions != null ? ` — ${e.sessions} sessions` : "";
      return `<dt>${pbEsc(warningLabels[k] || k.replace(/_/g, " "))}</dt>
        <dd>${pbEsc(e.thesis || "")}${pbEsc(hard)}${pbEsc(cond)}${pbEsc(sessions)}</dd>`;
    }).join("");
  const levels = [
    ["Entry", pbN(row.entry, 2)],
    [warning ? "Invalidation" : "Stop", pbN(row.stop, 2)],
    [warning ? "Downside" : "Target", pbN(row.target, 2)],
    ["R:R", row.rr != null ? pbN(row.rr, 2) : "—"],
    ["Risk", pbPct(row.risk_pct)],
    ["Hold", `${pbN(row.hold)} bars`],
    ["Confidence", row.confidence || "—"],
    ["Signal", warning ? "TOP WARNING" : "LONG ENTRY"],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd>${pbEsc(v)}</dd></div>`).join("");
  const indicators = row.indicators && Object.keys(row.indicators).length
    ? `<strong>Measured evidence</strong><pre>${pbEsc(JSON.stringify(row.indicators, null, 2))}</pre>`
    : "";
  const params = row.params && Object.keys(row.params).length
    ? `<strong>Rule parameters</strong><pre>${pbEsc(JSON.stringify(row.params, null, 2))}</pre>`
    : "";
  const overlaps = (row.overlaps || []).length
    ? `<p class="method-note">Also tagged by: ${pbEsc((row.overlaps || []).join(", "))}</p>`
    : "";
  document.getElementById("pbDetailBody").innerHTML = `
    <div class="pb-detail-meta">
      <span class="pb-chip">${pbEsc(m.family || "")}</span>
      <span class="pb-chip">${pbEsc(row.strategy)}</span>
      <span class="pb-chip">${pbEsc(row.status || "")}</span>
    </div>
    <dl class="pb-stats" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px">${levels}</dl>
    <p class="pb-formula" style="margin-bottom:14px">${pbEsc(row.notes || "")}</p>
    ${exitRows ? `<dl class="pb-exit">${exitRows}</dl>` : ""}
    ${overlaps}
    ${indicators}
    ${params}`;
  panel.hidden = false;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ------------------------------------------------------------------- load ---
async function pbLoadSignals(strategy, title, note) {
  const suffix = strategy
    ? `&strategy=${encodeURIComponent(strategy)}`
    : "";
  const data = await api(`/api/playbook/signals?limit=1000${suffix}`);
  pbRenderSignals(data.signals || [], title, note);
  return data;
}

async function loadPlaybook() {
  if (PB.loading) return;
  PB.loading = true;
  const grid = document.getElementById("pbStrategyGrid");
  try {
    if (grid && !PB.data) grid.innerHTML = `<p class="pb-empty">Loading the rule catalogue…</p>`;
    const data = await api("/api/playbook/strategies");
    PB.data = data;
    pbRenderCatalogue(data.strategies || []);
    pbRenderBacktests(data.strategies || []);
    pbRenderJobStatus(data);
    if (!PB.selected) {
      const title = PB.filter
        ? `Matches: ${pbMeta(PB.filter).name}`
        : "Latest tags";
      await pbLoadSignals(PB.filter, title);
    }
  } catch (err) {
    if (grid) grid.innerHTML = `<p class="pb-empty">Could not load the playbook: ${pbEsc(err.message)}</p>`;
    pbSetStatus("pbScanStatus", `Error: ${err.message}`, "warn");
  } finally {
    PB.loading = false;
  }
}
window.loadPlaybook = loadPlaybook;

// -------------------------------------------------------------------- jobs ---
function pbPollScan() {
  if (PB.scanTimer) return;
  const btn = document.getElementById("pbScanBtn");
  if (btn) btn.disabled = true;
  PB.scanTimer = setInterval(async () => {
    try {
      const s = await api("/api/playbook/scan/status");
      pbSetStatus("pbScanStatus", pbScanLabel(s), s.running ? "warn" : "");
      if (!s.running) {
        clearInterval(PB.scanTimer);
        PB.scanTimer = null;
        if (btn) btn.disabled = false;
        await loadPlaybook();
      }
    } catch (err) {
      clearInterval(PB.scanTimer);
      PB.scanTimer = null;
      if (btn) btn.disabled = false;
      pbSetStatus("pbScanStatus", `Status check failed: ${err.message}`, "warn");
    }
  }, 2500);
}

function pbPollBacktest() {
  if (PB.btTimer) return;
  const btn = document.getElementById("pbBacktestBtn");
  if (btn) btn.disabled = true;
  PB.btTimer = setInterval(async () => {
    try {
      const s = await api("/api/playbook/backtest/status");
      pbSetStatus("pbBacktestStatus", pbBtLabel(s), s.running ? "warn" : "");
      if (!s.running) {
        clearInterval(PB.btTimer);
        PB.btTimer = null;
        if (btn) btn.disabled = false;
        await loadPlaybook();
      }
    } catch (err) {
      clearInterval(PB.btTimer);
      PB.btTimer = null;
      if (btn) btn.disabled = false;
      pbSetStatus("pbBacktestStatus", `Status check failed: ${err.message}`, "warn");
    }
  }, 3000);
}

async function pbRunScan() {
  const btn = document.getElementById("pbScanBtn");
  if (btn) btn.disabled = true;
  pbSetStatus("pbScanStatus", "Starting the whole-universe scan…", "warn");
  try {
    const r = await api("/api/playbook/scan", { method: "POST" });
    if (r.already_running) pbSetStatus("pbScanStatus", "A scan is already running.", "warn");
    pbPollScan();
  } catch (err) {
    if (btn) btn.disabled = false;
    pbSetStatus("pbScanStatus", `Could not start the scan: ${err.message}`, "warn");
  }
}

async function pbRunBacktest() {
  const btn = document.getElementById("pbBacktestBtn");
  if (btn) btn.disabled = true;
  pbSetStatus("pbBacktestStatus",
    "Starting the walk-forward backtest (whole universe, every bar)…", "warn");
  try {
    const r = await api("/api/playbook/backtest", {
      method: "POST",
      body: JSON.stringify({ limit: 900, years: 3, step: 1 }),
    });
    if (r.error) throw new Error(r.error);
    if (r.already_running) pbSetStatus("pbBacktestStatus", "A backtest is already running.", "warn");
    pbPollBacktest();
  } catch (err) {
    if (btn) btn.disabled = false;
    pbSetStatus("pbBacktestStatus", `Could not start the backtest: ${err.message}`, "warn");
  }
}

// ------------------------------------------------------------------ events ---
function pbWire() {
  if (PB.wired) return;
  PB.wired = true;
  const grid = document.getElementById("pbStrategyGrid");
  if (grid) {
    grid.addEventListener("click", (event) => {
      const show = event.target.closest("[data-pb-show]");
      if (show) {
        const sid = show.dataset.pbShow;
        PB.filter = sid;
        PB.selected = null;
        pbLoadSignals(sid, `Matches: ${pbMeta(sid).name}`,
          "One click, one rule. Every tag below passed the exact filter.");
        const title = document.getElementById("pbResultsTitle");
        if (title) {
          const panel = title.closest(".pb-results") || title;
          panel.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        return;
      }
      const rule = event.target.closest("[data-pb-rule]");
      if (rule) {
        const el = document.getElementById(`pbRule-${rule.dataset.pbRule}`);
        if (el) el.hidden = !el.hidden;
      }
    });
  }
  const body = document.getElementById("pbSignalsBody");
  if (body) {
    body.addEventListener("click", (event) => {
      const tr = event.target.closest("tr[data-key]");
      if (!tr) return;
      const row = PB.signals.find((x) => pbKey(x) === tr.dataset.key);
      if (row) pbShowDetail(row);
    });
  }
  const scanBtn = document.getElementById("pbScanBtn");
  if (scanBtn) scanBtn.addEventListener("click", pbRunScan);
  const btBtn = document.getElementById("pbBacktestBtn");
  if (btBtn) btBtn.addEventListener("click", pbRunBacktest);
  const symBtn = document.getElementById("pbSymbolBtn");
  if (symBtn) symBtn.addEventListener("click", pbFindSymbol);
  const input = document.getElementById("pbSymbolInput");
  if (input) {
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") pbFindSymbol();
    });
  }
  const clear = document.getElementById("pbClearBtn");
  if (clear) {
    clear.addEventListener("click", async () => {
      PB.filter = null;
      PB.selected = null;
      const panel = document.getElementById("pbDetailPanel");
      if (panel) panel.hidden = true;
      await pbLoadSignals(null, "Latest tags", "Every match on the latest scan date.");
    });
  }
  const close = document.getElementById("pbDetailClose");
  if (close) {
    close.addEventListener("click", () => {
      const panel = document.getElementById("pbDetailPanel");
      if (panel) panel.hidden = true;
      PB.selected = null;
    });
  }
}

async function pbFindSymbol() {
  const input = document.getElementById("pbSymbolInput");
  const symbol = String((input && input.value) || "").trim().toUpperCase();
  if (!symbol) return;
  try {
    const data = await api(`/api/playbook/symbol/${encodeURIComponent(symbol)}`);
    PB.filter = null;
    const tags = data.tags || [];
    pbRenderSignals(tags, `Tags for ${symbol}`,
      data.as_of ? `Scan date ${data.as_of}. Every rule this stock satisfies.`
        : "No scan date yet.");
    if (tags.length) {
      pbShowDetail(tags[0]);
    } else {
      const panel = document.getElementById("pbDetailPanel");
      if (panel) panel.hidden = true;
    }
  } catch (err) {
    pbRenderSignals([], `Tags for ${symbol}`, `Lookup failed: ${err.message}`);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    pbWire();
    if (location.hash.replace("#", "").split("/")[0] === "playbook") loadPlaybook();
  });
} else {
  pbWire();
  if (location.hash.replace("#", "").split("/")[0] === "playbook") loadPlaybook();
}
