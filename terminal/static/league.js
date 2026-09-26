// League — 14 famous-trader books + OUR system, Rs 10 lakh play money each.
// Backtest = replay of the past (only data known on each day).
// Live     = paper trading from the league start, updated every evening.
// Engine: trader_league.py · API: /api/league/*

(function () {
  const S = { mode: null, exit: "book", selected: null, poll: null, chart: null };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inr = (v) => (v === null || v === undefined || Number.isNaN(v)) ? "—"
    : "₹" + Math.round(v).toLocaleString("en-IN");
  const pct = (v, d = 1) => (v === null || v === undefined) ? "—"
    : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;
  const pctAbs = (v, d = 1) => (v === null || v === undefined) ? "—"
    : `${(v * 100).toFixed(d)}%`;
  const num = (v, d = 2) => (v === null || v === undefined) ? "—" : Number(v).toFixed(d);
  const cls = (v) => (v === null || v === undefined) ? "" : (v >= 0 ? "lg-pos" : "lg-neg");
  const VERDICT = {
    READY: ["lg-ready", "READY"], PAPER: ["lg-paper", "PAPER FIRST"],
    NOT_READY: ["lg-notready", "NOT READY"], NO_DATA: ["lg-nodata", "NO DATA"],
  };
  const badge = (code) => {
    const v = VERDICT[code] || VERDICT.NO_DATA;
    return `<span class="lg-verdict ${v[0]}">${v[1]}</span>`;
  };

  async function loadLeague() {
    const root = document.getElementById("leagueRoot");
    if (!root) return;
    if (!root.dataset.ready) root.innerHTML = "<p>Loading league...</p>";
    let status = null, ov = null;
    try {
      status = await api("/api/league/status");
      if (!S.mode) {
        const runs = (status.runs || []).map((r) => r.run_id);
        S.mode = runs.includes("backtest-book") ? "backtest"
          : runs.includes("live-book") ? "live" : "backtest";
      }
      ov = await api(`/api/league/overview?mode=${S.mode}&exit=${S.exit}`);
    } catch (e) {
      root.innerHTML = `<p class="strategy-error">League unavailable: ${esc(e.message)}</p>`;
      return;
    }
    root.dataset.ready = "1";
    root.innerHTML = `
      ${controlsHtml()}
      <div class="lg-run">${runLine(ov)}</div>
      ${genomeHtml(ov.genome)}
      ${ov.error ? `<p class="strategy-error">${esc(ov.error)}</p>` : ""}
      ${ov.run ? homeHtml(ov) : emptyHtml()}
      ${ov.run ? tableHtml(ov) : ""}
      <div id="lgPlayer"></div>
      ${replayHtml(status, S.mode === "backtest" && !ov.run)}
      ${helpHtml()}`;
    bind(root, ov);
    if (S.selected && ov.run) loadPlayer(S.selected);
    schedulePoll(status);
  }
  window.loadLeague = loadLeague;

  // ---------------------------------------------------------------- pieces
  function controlsHtml() {
    const seg = (key, val, label) =>
      `<button class="${S[key] === val ? "on" : ""}" data-${key}="${val}">${label}</button>`;
    return `<div class="lg-controls">
      <div class="lg-seg">${seg("mode", "backtest", "🧪 Backtest")}${seg("mode", "live", "📡 Live league")}</div>
      <div class="lg-seg">${seg("exit", "book", "Book exits")}${seg("exit", "common", "Same exits for all")}</div>
      <button class="strategy-run-btn" id="lgResim" title="Recompute portfolios from stored signals (seconds)">↻ Re-simulate</button>
    </div>`;
  }

  function runLine(ov) {
    const r = ov.run;
    if (!r) return S.mode === "live"
      ? "Live league starts with the first evening run (weekdays 19:00 IST)."
      : "No backtest yet — start the pre-season replay below.";
    const b = r.bench_return !== null && r.bench_return !== undefined
      ? ` · ${esc(r.benchmark)} ${pct(r.bench_return)}` : "";
    return `${S.mode === "live" ? "Live paper league" : "Backtest"} ${esc(r.start)} → ${esc(r.end)}
      · ${r.days || "—"} trading days · ${r.stocks || "—"} stocks traded${b}
      · ₹10,00,000 each, after all costs · saved ${esc((r.created_at || "").replace("T", " "))}`;
  }

  function genomeHtml(genome) {
    if (!genome) return "";
    const table = (rows) => rows.length ? `
      <div class="lg-scroll"><table class="strategy-table lg-genome-table">
        <thead><tr><th>Playbook</th><th>Market mood</th><th>Method</th>
          <th style="text-align:right">Shared exits · N</th>
          <th style="text-align:right">Win</th><th style="text-align:right">Avg R</th>
          <th style="text-align:right">PF</th><th style="text-align:right">Book exits · Avg R</th>
        </tr></thead><tbody>${rows.map((cell) => `
          <tr><td>${esc(cell.name)}</td><td>${esc(cell.regime)}</td>
            <td>${esc(cell.method)}</td>
            <td style="text-align:right">${cell.common.trades}</td>
            <td style="text-align:right">${pctAbs(cell.common.win_rate, 0)}</td>
            <td style="text-align:right" class="${cls(cell.common.avg_r)}">${num(cell.common.avg_r, 2)}R</td>
            <td style="text-align:right">${num(cell.common.pf)}</td>
            <td style="text-align:right" class="${cls(cell.book && cell.book.avg_r)}">${cell.book ? `${num(cell.book.avg_r, 2)}R · N=${cell.book.trades}` : "—"}</td>
          </tr>`).join("")}</tbody></table></div>` : `<p class="lg-note">Not enough executed trades yet. A context needs at least ${genome.minimum_trades} shared-exit trades to appear.</p>`;
    const leaders = table(genome.leaders || []);
    const weak = table(genome.weak_spots || []);
    return `<details class="lg-details lg-genome">
      <summary>🧬 Signal Genome — where methods met market regimes</summary>
      <p class="lg-note">Contexts with the strongest and weakest historical average R under shared exits, requiring at least ${genome.minimum_trades} closed trades. Book-exit results are shown alongside to compare the full recipe. These are retrospective descriptions, not predictions.</p>
      <h4 class="lg-h4">Strongest historical contexts</h4>${leaders}
      <h4 class="lg-h4">Weakest historical contexts</h4>${weak}
      <p class="lg-note">${esc(genome.note || "")}</p>
    </details>`;
  }

  function emptyHtml() {
    return `<div class="lg-home"><h3>🏁 No ${S.mode === "live" ? "live" : "backtest"} results yet</h3>
      <p class="lg-note">${S.mode === "live"
        ? "The live league fills itself: every weekday at 19:00 IST the scheduler stores each book's signals and trades them on paper. First trades appear the day after the first run."
        : "Run the pre-season replay (below, or on the VM: <code>python trader_league.py replay --background</code>). It replays every past day for each book using only the data known that day, then simulates ₹10 lakh portfolios."}</p></div>`;
  }

  function homeHtml(ov) {
    const h = ov.home;
    if (!h || !h.readiness) {
      return `<div class="lg-home"><h3>🎯 Our System</h3><p class="lg-note">Our system has no ${S.mode} results in this run yet.</p></div>`;
    }
    const s = h.stats || {};
    const checks = (h.readiness.checks || []).map((c) => `
      <div class="lg-check"><span class="${c.ok ? "chk-ok" : "chk-fail"}">${c.ok ? "✓" : "✗"}</span>
        <span class="nm" title="${esc(c.why)}">${esc(c.name)}</span>
        <span class="vl">${esc(c.value ?? "—")}</span><span class="nd">need ${esc(c.need)}</span></div>`).join("");
    return `<div class="lg-home">
      <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:flex-start">
        <div><h3>🎯 Is our system ready for real money?</h3>
          <div class="lg-big">${inr(s.final_equity)} <span class="${cls(s.return_pct)}" style="font-size:15px">${pct(s.return_pct)}</span></div>
          <div class="lg-note" style="margin-top:2px">from ₹10,00,000 · ${s.trades ?? 0} trades · win ${pctAbs(s.win_rate, 0)} · PF ${num(s.pf)} · worst fall ${pctAbs(s.max_dd)} · costs paid ${inr(s.total_costs)}</div></div>
        <div>${badge(h.readiness.code)}</div>
      </div>
      <div style="margin-top:10px">${checks}</div>
      <p class="lg-note"><b>Verdict:</b> ${esc(h.readiness.verdict)}<br><b>Rules used:</b> ${esc(h.exit_rules || "")}</p>
    </div>`;
  }

  function tableHtml(ov) {
    const rows = ov.rows.filter((r) => r.playing);
    const idle = ov.rows.filter((r) => !r.playing);
    const body = rows.map((r) => `
      <tr class="strategy-row ${r.slug === "home" ? "lg-row-home" : ""}" data-slug="${esc(r.slug)}">
        <td>${r.rank}</td>
        <td><b>${r.slug === "home" ? "🎯 " : ""}${esc(r.name)}</b><div class="uc-dim" style="font-size:11px">${esc(r.book)}</div></td>
        <td style="text-align:right">${inr(r.final_equity)}</td>
        <td style="text-align:right" class="${cls(r.return_pct)}">${pct(r.return_pct)}</td>
        <td style="text-align:right" class="lg-hide-sm">${r.cagr === null || r.cagr === undefined ? "—" : pctAbs(r.cagr)}</td>
        <td style="text-align:right">${pctAbs(r.max_dd)}</td>
        <td style="text-align:right" class="lg-hide-sm">${pctAbs(r.win_rate, 0)}</td>
        <td style="text-align:right">${num(r.pf)}</td>
        <td style="text-align:right">${r.trades ?? 0}</td>
        <td>${badge(r.verdict_code)}</td>
      </tr>`).join("");
    const cards = rows.map((r) => `
      <div class="lg-card ${r.slug === "home" ? "lg-card-home" : ""}" data-slug="${esc(r.slug)}">
        <div class="lg-card-top"><span class="lg-rank">${r.rank}</span>
          <b>${r.slug === "home" ? "🎯 " : ""}${esc(r.name)}</b>${badge(r.verdict_code)}</div>
        <div class="lg-card-mid">${inr(r.final_equity)} <span class="${cls(r.return_pct)}">${pct(r.return_pct)}</span></div>
        <div class="lg-card-sub">Max DD ${pctAbs(r.max_dd)} · PF ${num(r.pf)} · win ${pctAbs(r.win_rate, 0)} · ${r.trades ?? 0} trades</div>
      </div>`).join("");
    const idleHtml = idle.length ? `<p class="lg-note">Not playing in this ${S.mode === "live" ? "league" : "backtest"}: ${
      idle.map((r) => `<b>${esc(r.name)}</b> (${esc(r.why_not || "no signals")})`).join(" · ")}</p>` : "";
    return `<div class="lg-cards">${cards}</div><div class="lg-scroll lg-wide"><table class="strategy-table lg-table">
      <thead><tr><th>#</th><th>Player</th><th style="text-align:right">Value</th><th style="text-align:right">Return</th>
      <th style="text-align:right" class="lg-hide-sm">CAGR</th><th style="text-align:right">Max DD</th><th style="text-align:right" class="lg-hide-sm">Win</th>
      <th style="text-align:right">PF</th><th style="text-align:right">Trades</th><th>Verdict</th></tr></thead>
      <tbody>${body}</tbody></table></div>${idleHtml}
      <p class="lg-note">Tap a player for the equity curve, every trade and which methods actually made money.
      ${S.exit === "common" ? "Same exits for all = setup stop (or 2×ATR), 2R target, 20-day time stop: a more comparable entry view, though fill timing and portfolio capacity still matter." : "Book exits = each book's own exit rules (EXIT_LOGIC.md)."}</p>`;
  }

  function replayHtml(st, openByDefault) {
    const job = (st && st.replay_job) || {};
    const rows = ((st && st.players) || []).filter((p) => p.backtest).map((p) => `
      <tr><td>${esc(p.name)}${p.code_changed ? ' <span class="chk-fail" title="Code or settings changed since the replay — on the VM run: python trader_league.py replay --changed --background">⚠</span>' : ""}</td>
      <td style="text-align:right">${(p.replay_signals || 0).toLocaleString("en-IN")}</td>
      <td style="text-align:right">${p.replay_stocks || 0}</td>
      <td class="lg-hide-sm">${p.replay_from ? esc(p.replay_from) + " → " + esc(p.replay_to) : "—"}</td>
      <td style="text-align:right">${(p.live_signals || 0).toLocaleString("en-IN")}</td></tr>`).join("");
    const tail = (job.log_tail || []).map(esc).join("<br>");
    return `<details class="lg-details" ${(job.running || openByDefault) ? "open" : ""}>
      <summary>⚙️ Pre-season replay ${job.running ? '<span class="lg-verdict lg-paper">RUNNING</span>' : ""}</summary>
      <p class="lg-note">Replays every past trading day for each chart book (and our system) using only the prices known that day, stores the buy signals, then simulates the portfolios. Slow the first time (about 1–1.5 hours for 300 stocks × 3 years on one fast core, longer on a small VM), resumable, and only new days are added later.</p>
      <div class="lg-controls">
        <label class="lg-note">Years <input id="lgYears" type="number" min="0.5" max="10" step="0.5" value="${job.years || 3}" style="width:60px"></label>
        <label class="lg-note">Stocks <input id="lgSyms" type="number" min="20" max="1500" step="50" value="${job.symbols || 300}" style="width:70px"></label>
        <label class="lg-note">Cores <input id="lgWorkers" type="number" min="1" max="8" value="${job.workers || 1}" style="width:50px"></label>
        <button class="strategy-run-btn" id="lgReplay" ${job.running ? "disabled" : ""}>${job.running ? "Running…" : "▶ Start / continue replay"}</button>
      </div>
      ${tail ? `<div class="lg-log">${tail}</div>` : ""}
      <div class="lg-scroll"><table class="strategy-table lg-cover"><thead><tr><th>Player</th><th style="text-align:right">Replay signals</th>
      <th style="text-align:right">Stocks</th><th class="lg-hide-sm">Replayed</th><th style="text-align:right">Live signals</th></tr></thead><tbody>${rows}</tbody></table></div>
    </details>`;
  }

  function helpHtml() {
    return `<details class="lg-details"><summary>❓ How to read the league</summary><div class="lg-note">
      <b>Value / Return</b> — what ₹10,00,000 became after STT (0.1% buy + sell), stamp duty, exchange + SEBI fees, GST, DP charges and 0.2% slippage per side.<br>
      <b>CAGR</b> — yearly growth rate. <b>Max DD</b> — worst fall from a peak (can you sit through it?).<br>
      <b>PF (profit factor)</b> — rupees won per rupee lost. Below 1.0 loses money; 1.3+ is the bar for real money.<br>
      <b>Verdict</b> — the real-money checklist: enough trades, PF, drawdown, beats Nifty, most years profitable, a Monte-Carlo bad-luck test, and live paper trades that confirm the backtest.<br>
      <b>Signal Genome</b> — groups executed trades by playbook, method, and market regime. Shared exits make entry approaches more comparable; Book exits measure each implemented recipe. It is historical description, not a prediction or causal test.<br>
      <b>Honest limits</b> — the backtest uses today's stock list (stocks that died are missing, so results look better than reality). The 4 fundamentals books and O'Neil's earnings checks need historical fundamentals we don't store, so they play only in the live league. Daily OHLC bars cannot reveal exact intraday price order; the conservative stop-first stress view helps show that uncertainty.
    </div></details>`;
  }

  // ---------------------------------------------------------------- player
  async function loadPlayer(slug) {
    const box = document.getElementById("lgPlayer");
    if (!box) return;
    S.selected = slug;
    document.querySelectorAll(".lg-table tr[data-slug], .lg-card[data-slug]").forEach((el) =>
      el.classList.toggle("lg-sel", el.dataset.slug === slug));
    box.innerHTML = "<p>Loading player...</p>";
    let d;
    try { d = await api(`/api/league/player/${encodeURIComponent(slug)}?mode=${S.mode}&exit=${S.exit}`); }
    catch (e) { box.innerHTML = `<p class="strategy-error">${esc(e.message)}</p>`; return; }
    if (!d.playing) {
      box.innerHTML = `<div class="strategy-block"><strong>${esc(d.name)}</strong><p class="lg-note">No results in this run. Exit rules: ${esc(d.exit_rules || "")}</p></div>`;
      return;
    }
    const s = d.stats || {};
    const stat = (label, val, c = "") => `<div class="lg-stat"><span>${label}</span><strong class="${c}">${val}</strong></div>`;
    const years = Object.entries(s.yearly || {}).map(([y, v]) =>
      `<span class="lg-chip ${cls(v.return)}">${esc(y)} ${pct(v.return)}</span>`).join(" ");
    const groupTable = (rows, key, title) => (rows && rows.length) ? `
      <h4 class="lg-h4">${title}</h4><div class="lg-scroll"><table class="strategy-table"><thead><tr><th>${key === "regime" ? "Market mood" : key === "reason" ? "Exit" : "Method"}</th>
      <th style="text-align:right">Trades</th><th style="text-align:right">Win</th><th style="text-align:right">PF</th><th style="text-align:right" class="lg-hide-sm">Avg R</th><th style="text-align:right">P&amp;L</th></tr></thead><tbody>
      ${rows.map((m) => `<tr><td class="lg-ell" title="${esc(m[key])}">${esc(m[key])}</td><td style="text-align:right">${m.trades}</td><td style="text-align:right">${pctAbs(m.win_rate, 0)}</td>
      <td style="text-align:right">${num(m.pf)}</td><td style="text-align:right" class="lg-hide-sm">${num(m.avg_r)}</td><td style="text-align:right" class="${cls(m.pnl)}">${inr(m.pnl)}</td></tr>`).join("")}
      </tbody></table></div>` : "";
    const checks = ((d.readiness || {}).checks || []).map((c) => `
      <div class="lg-check"><span class="${c.ok ? "chk-ok" : "chk-fail"}">${c.ok ? "✓" : "✗"}</span>
      <span class="nm" title="${esc(c.why)}">${esc(c.name)}</span><span class="vl">${esc(c.value ?? "—")}</span><span class="nd">need ${esc(c.need)}</span></div>`).join("");
    const opens = (d.open || []).length ? `<h4 class="lg-h4">Open positions (${d.open.length})</h4><div class="lg-scroll"><table class="strategy-table">
      <thead><tr><th>Symbol</th><th class="lg-hide-sm">Since</th><th style="text-align:right">Entry</th><th style="text-align:right" class="lg-hide-sm">Stop</th><th style="text-align:right">Last</th><th style="text-align:right">P&amp;L</th><th class="lg-hide-sm">Method</th></tr></thead><tbody>
      ${d.open.map((o) => `<tr class="strategy-row" data-sym="${esc(o.symbol)}"><td><b>${esc(o.symbol)}</b></td><td class="lg-hide-sm">${esc(o.entry_date)}</td>
      <td style="text-align:right">${num(o.entry_price)}</td><td style="text-align:right" class="lg-hide-sm">${num(o.stop)}</td><td style="text-align:right">${num(o.last_close)}</td>
      <td style="text-align:right" class="${cls(o.mtm_pnl)}">${inr(o.mtm_pnl)}</td><td class="uc-dim lg-hide-sm" style="font-size:11px">${esc(o.method)}</td></tr>`).join("")}</tbody></table></div>` : "";
    const trades = (d.trades || []).length ? `<h4 class="lg-h4">Last ${d.trades.length} closed trades</h4><div class="lg-scroll"><table class="strategy-table">
      <thead><tr><th>Symbol</th><th class="lg-hide-sm">In</th><th>Out</th><th style="text-align:right" class="lg-hide-sm">Buy</th><th style="text-align:right" class="lg-hide-sm">Sell</th><th style="text-align:right">P&amp;L</th><th style="text-align:right" class="lg-hide-sm">R</th><th>Exit</th><th class="lg-hide-sm">Method</th></tr></thead><tbody>
      ${d.trades.map((t) => `<tr class="strategy-row" data-sym="${esc(t.symbol)}"><td><b>${esc(t.symbol)}</b></td><td class="lg-hide-sm">${esc(t.entry_date)}</td><td>${esc(t.exit_date)}</td>
      <td style="text-align:right" class="lg-hide-sm">${num(t.entry_price)}</td><td style="text-align:right" class="lg-hide-sm">${num(t.exit_price)}</td>
      <td style="text-align:right" class="${cls(t.pnl)}">${inr(t.pnl)} <span class="uc-dim">${pct(t.pnl_pct)}</span></td>
      <td style="text-align:right" class="lg-hide-sm">${num(t.r_mult)}</td><td class="lg-ell">${esc(t.reason)}</td><td class="uc-dim lg-hide-sm" style="font-size:11px">${esc(t.method)}</td></tr>`).join("")}</tbody></table></div>` : "";

    box.innerHTML = `<div class="strategy-block lg-player">
      <div class="strategy-head"><div><strong>${d.slug === "home" ? "🎯 " : ""}${esc(d.name)}</strong>
        <div class="strategy-desc">${esc(d.book || "")}</div></div>${badge((d.readiness || {}).code)}</div>
      <p class="lg-note"><b>Exit rules:</b> ${esc(d.exit_rules || "")}</p>
      <div class="lg-grid">
        ${stat("Value", inr(s.final_equity))}${stat("Return", pct(s.return_pct), cls(s.return_pct))}
        ${stat("CAGR", s.cagr === null || s.cagr === undefined ? "—" : pctAbs(s.cagr))}${stat("Max drawdown", pctAbs(s.max_dd))}
        ${stat("Trades", s.trades ?? 0)}${stat("Win rate", pctAbs(s.win_rate, 0))}
        ${stat("Profit factor", num(s.pf))}${stat("Avg R / trade", num(s.expectancy_r))}
        ${stat("Avg hold", s.avg_bars === undefined ? "—" : `${s.avg_bars} d`)}${stat("Invested (avg)", pctAbs(s.exposure, 0))}
        ${stat("Costs paid", inr(s.total_costs))}${stat("Bad-luck DD (95%)", pctAbs(s.mc_dd95))}
        ${stat("Sharpe", num(s.sharpe))}${stat(esc(d.bench_label || "Benchmark"), pct(s.bench_return), cls(s.bench_return))}
      </div>
      <div class="lg-chart" id="lgChart"></div>
      <p class="lg-note">Blue = this player's ₹10 lakh · grey = ${esc(d.bench_label || "benchmark")} bought with the same ₹10 lakh.</p>
      ${years ? `<div style="margin:6px 0">${years}</div>` : ""}
      ${checks ? `<h4 class="lg-h4">Real-money checklist</h4>${checks}` : ""}
      ${groupTable(d.by_method, "method", "Which methods made money")}
      ${groupTable(d.by_regime, "regime", "Results by market mood at entry")}
      ${groupTable(d.by_reason, "reason", "How trades ended")}
      ${opens}${trades}
    </div>`;
    drawChart(d);
    box.querySelectorAll("tr[data-sym]").forEach((tr) => tr.addEventListener("click", () => {
      if (typeof setView === "function" && typeof loadSymbol === "function") {
        setView("research"); loadSymbol(tr.dataset.sym);
      }
    }));
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function drawChart(d) {
    const el = document.getElementById("lgChart");
    if (S.chart) { try { S.chart.remove(); } catch (e) {} S.chart = null; }
    if (!el || typeof LightweightCharts === "undefined" || !(d.equity || []).length) {
      if (el) el.style.display = "none";
      return;
    }
    const chart = LightweightCharts.createChart(el, {
      height: el.clientHeight || 260, width: el.clientWidth || 600,
      layout: { background: { type: "solid", color: "transparent" }, textColor: "#9fb0cc" },
      grid: { vertLines: { color: "rgba(255,255,255,.04)" }, horzLines: { color: "rgba(255,255,255,.04)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,.1)" },
      timeScale: { borderColor: "rgba(255,255,255,.1)" },
      localization: { locale: "en-IN",
        priceFormatter: (p) => "₹" + Math.round(p).toLocaleString("en-IN") },
    });
    if ((d.bench || []).length) {
      chart.addLineSeries({ color: "rgba(159,176,204,.6)", lineWidth: 1 })
        .setData(d.bench.map(([t, v]) => ({ time: t, value: v })));
    }
    chart.addLineSeries({ color: "#60a5fa", lineWidth: 2 })
      .setData(d.equity.map(([t, v]) => ({ time: t, value: v })));
    chart.timeScale().fitContent();
    S.chart = chart;
    new ResizeObserver(() => { if (S.chart === chart) chart.applyOptions({ width: el.clientWidth }); }).observe(el);
  }

  // ---------------------------------------------------------------- events
  function bind(root, ov) {
    root.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => {
      S.mode = b.dataset.mode; loadLeague();
    }));
    root.querySelectorAll("[data-exit]").forEach((b) => b.addEventListener("click", () => {
      S.exit = b.dataset.exit; loadLeague();
    }));
    root.querySelectorAll(".lg-table tr[data-slug], .lg-card[data-slug]").forEach((el) =>
      el.addEventListener("click", () => loadPlayer(el.dataset.slug)));
    const rs = document.getElementById("lgResim");
    if (rs) rs.addEventListener("click", async () => {
      rs.disabled = true; rs.textContent = "Simulating…";
      try { await api(`/api/league/simulate?mode=${S.mode}`, { method: "POST" }); } catch (e) {}
      setTimeout(loadLeague, 2500);
    });
    const rp = document.getElementById("lgReplay");
    if (rp) rp.addEventListener("click", async () => {
      const y = document.getElementById("lgYears").value || 3;
      const n = document.getElementById("lgSyms").value || 300;
      const w = document.getElementById("lgWorkers").value || 1;
      if (!confirm(`Start the replay (${y} years, ${n} stocks, ${w} core${w > 1 ? "s" : ""})?\nIt runs in the background at low priority; you can close this page.`)) return;
      rp.disabled = true; rp.textContent = "Starting…";
      try {
        const r = await api(`/api/league/replay?years=${y}&symbols=${n}&workers=${w}`, { method: "POST" });
        if (!r.started) alert(r.reason || "Could not start the replay.");
      } catch (e) { alert("Could not start: " + e.message); }
      setTimeout(loadLeague, 1500);
    });
  }

  function schedulePoll(status) {
    if (S.poll) { clearTimeout(S.poll); S.poll = null; }
    const busy = (status && status.replay_job && status.replay_job.running) ||
                 (status && status.sim_job && status.sim_job.running);
    if (!busy) return;
    S.poll = setTimeout(() => {
      const v = document.getElementById("view-league");
      if (v && v.classList.contains("active-view")) loadLeague();
    }, 15000);
  }
})();
