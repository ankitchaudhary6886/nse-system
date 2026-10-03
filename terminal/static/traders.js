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
    box.querySelectorAll(".trader-tab").forEach(btn => {
      btn.addEventListener("click", () => {
        box.querySelectorAll(".trader-tab").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectTrader(btn.dataset.slug);
      });
    });
    selectTrader(_tradersCache[0].slug);
  } catch (e) {
    box.innerHTML = `<p>Error loading traders: ${e.message}</p>`;
  }
}
window.loadTradersIndex = loadTradersIndex;

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
        ${t.methods.map((m, index) => `<tr class="click-row" tabindex="0"
          role="button" data-method-index="${index}"
          aria-label="Open method details for ${m.name}">
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
  panel.querySelectorAll("[data-method-index]").forEach((row) => {
    const method = t.methods[Number(row.dataset.methodIndex)];
    const open = () => openMethodGuide(t, method);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
  const btn = document.getElementById("traderScanBtn");
  if (btn) btn.addEventListener("click", () => runTraderScan(slug));
}

function openMethodGuide(trader, method, signal) {
  const dialog = document.getElementById("dataDetailDialog");
  const heading = document.getElementById("dataDetailTitle");
  const body = document.getElementById("dataDetailBody");
  const guide = document.getElementById("methodGuideBody");
  if (!dialog || !heading || !body || !guide) return;

  heading.textContent = `${trader.name} · ${method.name || method.id || "Method"}`;
  body.classList.add("hidden");
  body.style.display = "none";
  guide.replaceChildren();
  guide.classList.remove("hidden");

  const paragraph = (text, className) => {
    const element = document.createElement("p");
    element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const addField = (label, value) => {
    if (value == null || value === "") return;
    const row = document.createElement("div");
    row.className = "level";
    const name = document.createElement("span");
    name.textContent = label;
    const detail = document.createElement("strong");
    detail.textContent = String(value);
    row.append(name, detail);
    guide.appendChild(row);
  };

  guide.appendChild(paragraph(trader.source || "", "method-guide-source"));
  guide.appendChild(paragraph(method.description ||
    "The registry does not include a plain-language description for this method."));
  guide.appendChild(document.createElement("h3")).textContent = "How to apply it";
  const checks = Array.isArray(method.conditions) && method.conditions.length
    ? method.conditions.map(condition =>
      `${condition.field || "Condition"} ${condition.op || ""} ${condition.value ?? ""}`.trim())
    : [];
  const steps = [
    `Read the stated rule: ${method.description || "Confirm the rule with its source before using it."}`,
    checks.length
      ? `Verify each registered condition: ${checks.join("; ")}.`
      : "Check the stated price, trend, volume, or company-quality conditions against the current data shown for the stock.",
    signal
      ? `The current scan returned ${signal.signal_type || "a match"} for this symbol as of ${signal.date || "the latest stored scan"}.`
      : "Use this trader's Run Scan to see whether the rule currently matches any symbol.",
    "Before considering any trade, independently define entry, invalidation/stop, position risk, and exit. Do not invent missing levels; some research screens intentionally provide no trade levels.",
  ];
  const list = document.createElement("ol");
  steps.forEach(text => {
    const item = document.createElement("li");
    item.textContent = text;
    list.appendChild(item);
  });
  guide.appendChild(list);
  addField("Direction", method.direction || signal?.direction || "not specified");
  addField("Scanner status", method.scan === false
    ? "Not implemented as an automated scan"
    : "Implemented scan; a match is not a validated win probability");
  if (signal) {
    guide.appendChild(document.createElement("h3")).textContent = "Current scan result";
    addField("Signal", signal.signal_type);
    addField("Entry reference", signal.entry);
    addField("Stop", signal.stop);
    addField("Target", signal.target);
    addField("Scanner note", signal.notes);
  }
  guide.appendChild(paragraph(
    "Research only. A scan match is not a recommendation or an order; confidence labels are not calibrated probabilities.",
    "method-warning"));
  if (!dialog.open) dialog.showModal();
}
window.openMethodGuide = openMethodGuide;

async function runTraderScan(slug) {
  const btn = document.getElementById("traderScanBtn");
  const box = document.getElementById("traderSignals");
  if (!box) return;
  if (btn) { btn.textContent = "Scanning..."; btn.disabled = true; }
  box.innerHTML = `<p>Scanning the band universe (~800 symbols). This may take 30-60s...</p>`;
  try {
    const r = await api(`/api/traders/${encodeURIComponent(slug)}/scan?limit=800`);
    if (r.error) {
      box.textContent = r.error;
    } else {
      box.innerHTML = _renderTraderSignals(r);
      _bindTraderSignalRows(box);
    }
  } catch (e) {
    box.textContent = e.message;
  }
  if (btn) { btn.textContent = "Run Scan (all methods)"; btn.disabled = false; }
}

function _renderTraderSignals(r) {
  const sigs = r.signals || [];
  if (!sigs.length) {
    return `<h3 style="font-size:14px;">Signals (0)</h3>
      <p class="strategy-hint">No signals across the universe today.</p>`;
  }
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
        return `<tr class="strategy-row click-row" tabindex="0" role="button"
          aria-label="Open research for ${s.symbol}" data-sym="${s.symbol}">
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
    const open = () => {
      const sym = row.dataset.sym;
      if (!sym) return;
      window.openSymbolResearch?.(sym);
    };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

let _matchedSymbol = null;
let _matchRequestId = 0;
async function loadTraderMatches(symbol) {
  const box = document.getElementById("traderMatchBox");
  const btn = document.getElementById("refreshTraderMatches");
  if (!box || !symbol) return;
  const requestId = ++_matchRequestId;
  _matchedSymbol = symbol.trim().toUpperCase();
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Checking…";
  }
  box.textContent = `Checking the registered trader rules for ${_matchedSymbol}…`;
  try {
    const data = await api(`/api/traders/matches/${encodeURIComponent(_matchedSymbol)}`);
    if (requestId !== _matchRequestId) return;
    if (data.error) throw new Error(data.error);
    if (!data.in_scan_universe) {
      box.textContent = data.message || "This symbol is outside the current trader scan universe.";
      return;
    }
    box.replaceChildren();
    const status = document.createElement("p");
    status.className = "method-note";
    status.textContent = `${data.n_methods_matched} method matches across ${data.n_traders_checked} traders · price data as of ${data.as_of || "date unavailable"}. Matches are rule hits, not win probabilities.`;
    box.appendChild(status);
    if (data.errors?.length) {
      const warning = document.createElement("p");
      warning.className = "method-warning";
      warning.textContent = `Some scans were unavailable (${data.errors.map(item => item.trader).join(", ")}). The results are incomplete.`;
      box.appendChild(warning);
    }
    if (!data.matches?.length) {
      const empty = document.createElement("p");
      empty.textContent = "No registered trader scan matched this symbol on the latest stored price data.";
      box.appendChild(empty);
      return;
    }
    data.matches.forEach(item => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "method-match";
      const title = document.createElement("strong");
      title.textContent = `${item.method.name} · ${item.trader}`;
      const details = document.createElement("span");
      details.textContent = item.method.description || item.signal.notes ||
        "Open the method guide for rule and risk context.";
      button.append(title, details);
      button.addEventListener("click", () =>
        openMethodGuide(
          { name: item.trader, source: item.source },
          item.method, item.signal));
      box.appendChild(button);
    });
  } catch (error) {
    if (requestId === _matchRequestId) {
      box.textContent = `Trader method check unavailable: ${error.message}`;
    }
  } finally {
    if (btn && requestId === _matchRequestId) {
      btn.disabled = !_matchedSymbol;
      btn.textContent = "Check methods";
    }
  }
}
window.loadTraderMatches = loadTraderMatches;

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshTraderMatches");
  if (btn) btn.addEventListener("click", () => {
    if (_matchedSymbol) loadTraderMatches(_matchedSymbol);
  });
});