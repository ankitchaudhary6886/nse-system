// Research Cockpit — per-symbol deep dive.
//
// WHAT CHANGED (slider work, kept separate from the existing read-outs):
//   * the panel now ends with a "what-if" box built from window.makeSlider
//     (terminal/static/sliders.js), which is injected here because index.html
//     is owned elsewhere;
//   * the box holds the buying price, the safety line, money in, risk %, and a
//     date window; every drag recomputes shares / money / most-you-lose in the
//     browser, so a drag never waits on the network;
//   * the date window re-renders the "Recent historical setups" table from
//     data already in the payload (raw_setups carries a per-row signal_date);
//   * the server is asked only when the buying price or the safety line change
//     (debounced 250 ms, one request in flight, cached per trigger/stop/shape);
//   * if the sizing call fails, the box keeps working and shows one sentence.
// No existing function was removed or made unreachable; renderResearch still
// takes the same payload and still writes into #researchBox.

let _researchRequestId = 0;
let _researchState = null;   // last payload + the numbers the sliders start from
let _slidersLoading = null;  // promise for the one-time sliders.js injection
let _slidersBound = null;    // the panel element the sliders were built into

/* --------------------------------------------------------------- helpers -- */

function _researchRow(label, value, colour) {
  const col = colour || "#edf3ff";
  return `<div class="fx-row" style="padding:8px 12px;">
    <span>${label}</span>
    <strong style="color:${col};">${value}</strong>
  </div>`;
}
function _pctStr(x) {
  if (x === null || x === undefined) return "—";
  return (x * 100).toFixed(0) + "%";
}
function _num(x, dp) {
  if (x === null || x === undefined) return "—";
  return Number(x).toFixed(dp === undefined ? 2 : dp);
}
/* Whole rupees in the Indian grouping the owner reads on the broker screen. */
function _rs(x) {
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  const neg = n < 0;
  const parts = Math.round(Math.abs(n)).toString().split("");
  let out;
  if (parts.length <= 3) {
    out = parts.join("");
  } else {
    const last3 = parts.slice(-3).join("");
    const rest = parts.slice(0, -3).join("").replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    out = rest + "," + last3;
  }
  return (neg ? "-₹" : "₹") + out;
}
function _esc(t) {
  return String(t == null ? "" : t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function _shortDate(d) {
  const s = String(d || "");
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s.slice(8) + "/" + s.slice(5, 7) : s;
}
/* Money inside an editable box: plain digits, so the phone keypad behaves. */
function _moneyInputValue(x) {
  const n = Number(x);
  return Number.isFinite(n) ? String(Math.round(n)) : "";
}

const _RESEARCH_INR = typeof Intl !== "undefined" && Intl.NumberFormat
  ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 })
  : null;
function _rsIntl(x) {
  const n = Number(x);
  if (!Number.isFinite(n) || !_RESEARCH_INR) return _rs(x);
  return "₹" + _RESEARCH_INR.format(Math.round(n));
}

/* Load sliders.js once, at runtime, without touching index.html. Resolves to
   true when window.makeSlider is available. */
function _loadSliders() {
  if (typeof window.makeSlider === "function") return Promise.resolve(true);
  if (_slidersLoading) return _slidersLoading;
  _slidersLoading = new Promise((resolve) => {
    const existing = document.querySelector('script[data-sliders-js="1"]');
    const done = () => resolve(typeof window.makeSlider === "function");
    if (existing) {
      existing.addEventListener("load", done);
      existing.addEventListener("error", done);
      return;
    }
    const s = document.createElement("script");
    s.src = "/static/sliders.js?v=1";
    s.async = true;
    s.setAttribute("data-sliders-js", "1");
    s.addEventListener("load", done);
    s.addEventListener("error", () => resolve(false));
    document.head.appendChild(s);
  });
  return _slidersLoading;
}

/* ------------------------------------------------------- candle / signature */

function _renderCandleBlock(data) {
  const cs = data.candle_stats || {};
  const currentType = data.current_setup && data.current_setup.mother_type;
  const keys = Object.keys(cs);
  if (!keys.length) return "";
  keys.sort((a, b) => (cs[b].n_setups || 0) - (cs[a].n_setups || 0));
  let html = `<h4 style="margin:14px 0 8px; font-size:13px;">🕯️ Candle behaviour (mother-bar classification)</h4>`;
  if (currentType) {
    html += `<div class="fx-row" style="padding:8px 12px; border-left:3px solid #60a5fa;">
      <span>Today's mother bar</span>
      <strong>${currentType}</strong>
    </div>`;
  }
  html += `<table style="width:100%; border-collapse:collapse; font-size:12px;">
    <thead><tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
      <th style="padding:6px 4px;">Type</th>
      <th style="padding:6px 4px;">n</th>
      <th style="padding:6px 4px;">trig</th>
      <th style="padding:6px 4px;">P+1R</th>
      <th style="padding:6px 4px;">P+2R</th>
      <th style="padding:6px 4px;">P+3R</th>
      <th style="padding:6px 4px;">MFE</th>
      <th style="padding:6px 4px;">MAE</th>
    </tr></thead><tbody>`;
  keys.forEach(k => {
    const s = cs[k];
    const n = s.n_setups || 0;
    const isCurrent = (k === currentType);
    const rowStyle = isCurrent
      ? "border-bottom:1px solid rgba(255,255,255,.05); background:rgba(96,165,250,.10);"
      : "border-bottom:1px solid rgba(255,255,255,.05);";
    const relClass = n >= 10 ? "rel-strong" : n >= 5 ? "rel-mod" : "rel-thin";
    html += `<tr class="click-row" tabindex="0" role="button"
      data-candle-key="${k}" style="${rowStyle}">
      <td style="padding:6px 4px;"><b>${k}</b>${isCurrent ? " ←" : ""}</td>
      <td style="padding:6px 4px;"><span class="rel-pill ${relClass}">${n}</span></td>
      <td style="padding:6px 4px;">${s.n_triggered || 0}</td>
      <td style="padding:6px 4px;">${_pctStr(s.p_1r)}</td>
      <td style="padding:6px 4px;">${_pctStr(s.p_2r)}</td>
      <td style="padding:6px 4px;">${_pctStr(s.p_3r)}</td>
      <td style="padding:6px 4px;">${_num(s.median_mfe_r)}R</td>
      <td style="padding:6px 4px;">${_num(s.median_mae_r)}R</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  return html;
}

function _renderSignatureBlock(data) {
  const sm = data.signature_match;
  if (!sm) return "";
  if (sm.error) {
    return `<h4 style="margin:14px 0 8px; font-size:13px;">🎯 Signature match</h4>
      <p style="color:#fbbf24; font-size:12px;">${sm.error}</p>`;
  }
  const sectors = Object.entries(sm.match_sectors || {})
    .sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([k, v]) => `${k}:${v}`).join(" · ");
  const outcomes = Object.entries(sm.outcome_mix || {})
    .map(([k, v]) => `${k}:${v}`).join(" · ");
  let html = `<h4 style="margin:14px 0 8px; font-size:13px;">🎯 Signature match — ${sm.k} nearest of ${sm.n_pool} pool setups</h4>`;
  html += `<div class="fx-row" style="padding:8px 12px;">
    <span>Hit rate (given trigger)<span class="ledger-sight" data-explain="hit_rate" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does hit rate mean?">?</span></span>
    <strong>+1R ${_pctStr(sm.p_1r)} · +2R ${_pctStr(sm.p_2r)} · +3R ${_pctStr(sm.p_3r)}</strong>
  </div>`;
  html += `<div class="fx-row" style="padding:8px 12px;">
    <span>MFE in R<span class="ledger-sight" data-explain="mfe" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does MFE mean?">?</span></span>
    <strong>median ${_num(sm.median_mfe_r)} · p95 ${_num(sm.p95_mfe_r)}</strong>
  </div>`;
  html += `<div class="fx-row" style="padding:8px 12px;">
    <span>MAE in R<span class="ledger-sight" data-explain="mae" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does MAE mean?">?</span></span>
    <strong>median ${_num(sm.median_mae_r)} · p5 ${_num(sm.p5_mae_r)}</strong>
  </div>`;
  html += _researchRow("Outcome mix", outcomes);
  html += _researchRow("Top sectors in matches", sectors);

  if (sm.sample_matches && sm.sample_matches.length) {
    html += `<details style="margin-top:8px;">
      <summary style="cursor:pointer; color:#9fb0cc; font-size:12px;">Show 15 sample matches</summary>
      <table style="width:100%; border-collapse:collapse; font-size:12px; margin-top:8px;">
        <thead><tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
          <th style="padding:6px 4px;">Symbol</th>
          <th style="padding:6px 4px;">Date</th>
          <th style="padding:6px 4px;">Outcome</th>
          <th style="padding:6px 4px;">MFE</th>
          <th style="padding:6px 4px;">MAE</th>
        </tr></thead><tbody>`;
    sm.sample_matches.forEach((m, index) => {
      const oc = m.outcome === "WIN" ? "chk-ok"
               : m.outcome === "LOSS" ? "chk-fail" : "";
      html += `<tr class="click-row" tabindex="0" role="button"
        aria-label="Open research for ${m.symbol}" data-match-index="${index}"
        style="border-bottom:1px solid rgba(255,255,255,.05);">
        <td style="padding:6px 4px;"><b>${m.symbol}</b></td>
        <td style="padding:6px 4px;">${m.signal_date}</td>
        <td style="padding:6px 4px;"><span class="${oc}">${m.outcome || "?"}</span></td>
        <td style="padding:6px 4px;">${_num(m.mfe_r)}R</td>
        <td style="padding:6px 4px;">${_num(m.mae_r)}R</td>
      </tr>`;
    });
    html += `</tbody></table></details>`;
  }
  return html;
}

/* ------------------------------------------- the "what-if" slider numbers -- */

/* The date window and the server call both need a remembered state, because a
   drag rebuilds the panel's inner HTML. */
function _initResearchState(data) {
  const cur = data.current_setup || {};
  const closeNow = Number(data.latest_close);
  const hasClose = Number.isFinite(closeNow) && closeNow > 0;
  const srv = data.sizing_response || {};
  const srvTrigger = Number(srv.trigger);
  const srvStop = Number(srv.stop);
  const capital = Number(srv.capital) > 0 ? Number(srv.capital) : 500000;

  let trigger = null;
  if (Number.isFinite(srvTrigger) && srvTrigger > 0) trigger = srvTrigger;
  else if (Number.isFinite(Number(cur.entry)) && Number(cur.entry) > 0) trigger = Number(cur.entry);
  else if (hasClose) trigger = closeNow;

  let stop = null;
  if (Number.isFinite(srvStop) && srvStop > 0) stop = srvStop;
  else if (Number.isFinite(Number(cur.stop)) && Number(cur.stop) > 0) stop = Number(cur.stop);
  else if (trigger != null) stop = Number((trigger * 0.99).toFixed(2));

  /* Only reuse the server's risk when it actually reports one for these prices;
     otherwise start from the system's own 1%-of-capital rule. */
  let riskPct = 1;
  if (Number.isFinite(srvTrigger) && Math.abs(srvTrigger - (trigger || 0)) < 0.01
      && Number(srv.risk_per_trade_pct) > 0) {
    riskPct = Number(srv.risk_per_trade_pct);
  }

  return {
    data: data,
    capital: capital,
    riskPct: riskPct,
    dateDays: 1000,
    live: { trigger: trigger, stop: stop },
    dateTable: null,
    dateMax: 1000
  };
}

function _getResearchState(data) {
  const st = _researchState;
  if (st && st.data === data) return st;
  return _initResearchState(data);
}

/* Mirror of sizing.suggest: the same caps, so the on-screen number matches the
   server's rule instead of inventing a friendlier one. Capital and risk come
   from the sliders themselves; the trigger/stop pair is passed in because the
   server ask depends on exactly those two numbers. */
function _scenarioNumbers(st, trigger, stop) {
  const data = st.data;
  const srv = data.sizing_response || {};
  const inCap = document.getElementById("sld-whatIfCapital");
  const inRisk = document.getElementById("sld-whatIfRisk");
  const capital = Number(inCap ? inCap.value : st.capital);
  const defRiskPct = Number(srv.risk_per_trade_pct) > 0 ? Number(srv.risk_per_trade_pct) : 1;
  const riskPct = Number(inRisk ? inRisk.value : st.riskPct);
  const maxAllocPct = Number(srv.max_alloc_pct) > 0 ? Number(srv.max_alloc_pct) : 25;
  const allocFactor = Number.isFinite(Number(srv.alloc_pct)) && Number(srv.alloc_pct) > 0
    ? Number(srv.alloc_pct) / maxAllocPct
    : 1;

  const out = {
    usable: false, why: "", shares: 0, invest: 0, loss: 0,
    lossPct: 0, investPct: 0, priceRiskPct: 0, binding: "",
    capital: capital, defRiskPct: defRiskPct, riskPct: riskPct,
    maxAllocPct: maxAllocPct, roomPct: maxAllocPct * allocFactor
  };
  if (!(capital > 0)) { out.why = "Enter how much money you are working with."; return out; }
  if (!(trigger > 0) || !(stop > 0)) {
    out.why = "Enter the buying price and the safety line to see shares and the most you could lose.";
    return out;
  }
  if (trigger <= stop) {
    out.why = "The safety line has to be below the buying price, because that gap is what you are risking.";
    return out;
  }
  const priceRisk = (trigger - stop) / trigger;
  const riskFraction = Math.min(defRiskPct / 100, (riskPct / 100) * allocFactor);
  const alloc = Math.min(maxAllocPct / 100, (maxAllocPct / 100) * allocFactor);
  const riskValue = capital * riskFraction;
  const valueByRisk = priceRisk > 0 ? riskValue / priceRisk : 0;
  const positionLimit = capital * alloc;
  const valueLimit = Math.min(positionLimit, valueByRisk);
  const shares = Math.floor(valueLimit / trigger);
  const invest = shares * trigger;
  const loss = shares * (trigger - stop);
  out.usable = true;
  out.shares = shares;
  out.invest = invest;
  out.loss = loss;
  out.priceRiskPct = priceRisk * 100;
  out.investPct = capital > 0 ? invest / capital * 100 : 0;
  out.lossPct = capital > 0 ? loss / capital * 100 : 0;
  out.binding = valueByRisk < positionLimit ? "the most you are willing to lose" : "the rule that no single idea gets more than " + _num(maxAllocPct, 2) + "% of your money";
  if (shares < 1) {
    out.why = "At these prices and limits one share is already too much, so the safe answer is none. Try a higher amount, or a safety line closer to the buying price.";
  }
  return out;
}

function _renderWhatIfPanel(data) {
  return `<div class="slider-panel" id="whatIfPanel">
    <h4>🎚️ Try your own numbers</h4>
    <p class="slider-lead">Drag anything below and the answer changes as you drag. Nothing is saved and nothing is bought — this is only arithmetic on the numbers you pick.</p>
    <div class="slider-price-row">
      <label class="slider-price" for="whatIfTrigger"><span>Price you would pay</span>
        <input type="number" id="whatIfTrigger" inputmode="decimal" min="0" step="0.05" aria-label="Price you would pay for one share"></label>
      <label class="slider-price" for="whatIfStop"><span>Safety line (you would sell here)</span>
        <input type="number" id="whatIfStop" inputmode="decimal" min="0" step="0.05" aria-label="Safety line price"></label>
    </div>
    <button type="button" class="slider-ghost" id="whatIfUseClose">Use the latest close as the buying price</button>
    <div id="whatIfSliders"></div>
    <p class="slider-note is-warn" id="wiWarn" hidden></p>
    <div class="slider-out" id="whatIfOut" aria-live="polite">
      <div class="fx-row"><span>Shares you could buy at that price<span class="ledger-sight" data-explain="sizing" tabindex="0" role="button" title="Tap to learn what this means" aria-label="What does how much money to put in mean?">?</span></span>
        <strong class="wi-big" id="wiShares">—</strong></div>
      <div class="fx-row"><span>What those shares cost</span><strong id="wiInvest">—</strong></div>
      <div class="fx-row"><span>Most you could lose if the safety line is hit<span class="ledger-sight" data-explain="stop" tabindex="0" role="button" title="Tap to learn what this means" aria-label="What does the safety line mean?">?</span></span>
        <strong class="wi-bad" id="wiLoss">—</strong></div>
      <div class="fx-row"><span>That loss, as a share of your money</span><strong id="wiLossPct">—</strong></div>
      <div class="fx-row"><span>Drop from your buying price down to the safety line<span class="ledger-sight" data-explain="risk_pct" tabindex="0" role="button" title="Tap to learn what this means" aria-label="What does how much you are risking mean?">?</span></span>
        <strong id="wiPriceRisk">—</strong></div>
      <div class="fx-row" id="wiRoomRow" hidden><span>Most the rules let one idea take</span><strong id="wiRoom">—</strong></div>
    </div>
    <p class="slider-note slider-date-note" id="dateWindowEffect"></p>
    <p class="slider-note is-warn" id="wiPad" hidden></p>
    <p class="slider-note" id="whatIfNote"></p>
  </div>`;
}

function _setText(id, value, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
  if (cls !== undefined) el.className = cls;
}

/* Everything drawn here is computed in the browser from the payload already on
   screen, so dragging never waits for the network. */
function _updateWhatIf() {
  const p = _whatIfParams();
  const box = document.getElementById("whatIfOut");
  if (!p || !box) return;
  const n = p.nums;
  _setText("wiShares", n.usable ? String(n.shares) : "none", "wi-big");
  _setText("wiInvest", n.usable ? _rsIntl(n.invest) : "—");
  _setText("wiLoss", n.usable ? _rsIntl(n.loss) : "—", "wi-bad");
  _setText("wiLossPct", n.usable ? _num(n.lossPct, 2) + "% of your money" : "—");
  _setText("wiPriceRisk", n.usable ? _num(n.priceRiskPct, 2) + "%" : "—");
  _setText("wiRoom", _rsIntl(n.capital * n.roomPct / 100));

  const warn = document.getElementById("wiWarn");
  if (warn) {
    if (!n.usable && n.why) { warn.textContent = n.why; warn.hidden = false; }
    else { warn.textContent = ""; warn.hidden = true; }
  }
  const room = document.getElementById("wiRoomRow");
  if (room) room.hidden = !(n.usable && n.shares > 0);

  const pad = document.getElementById("wiPad");
  if (pad) {
    const risky = n.riskPct > n.defRiskPct + 0.001;
    const loose = n.riskPct < n.defRiskPct - 0.001;
    if (n.usable && risky && n.shares > 0) {
      pad.textContent = "Careful: " + _num(n.riskPct, 2) + "% is more than the "
        + _num(n.defRiskPct, 2) + "% this system normally risks on one idea. On a bad run the losses add up faster than this.";
      pad.className = "slider-note is-warn";
      pad.hidden = false;
    } else if (n.usable && loose && n.shares > 0) {
      pad.textContent = "You are risking less than the " + _num(n.defRiskPct, 2)
        + "% this system normally risks, so the position is smaller and a losing run bites less.";
      pad.className = "slider-note";
      pad.hidden = false;
    } else {
      pad.textContent = "";
      pad.hidden = true;
    }
  }

  const note = document.getElementById("whatIfNote");
  if (note) {
    const bits = [];
    if (n.usable && n.shares > 0) bits.push("What limits the quantity here is " + n.binding + ".");
    bits.push("A fall to the safety line is the planned loss only — a gap, a bad fill, fees and taxes can all make it worse.");
    if (n.usable && n.shares > 0) {
      bits.push("The price you actually get can be worse than " + _num(p.trigger, 2) + ", which makes the loss bigger.");
    }
    bits.push("The amounts and the risk are worked out instantly in your browser. The server is asked only when you change the buying price or the safety line.");
    note.textContent = bits.join(" ");
  }
}

function _whatIfParams() {
  const st = _researchState;
  if (!st) return null;
  const tEl = document.getElementById("whatIfTrigger");
  const sEl = document.getElementById("whatIfStop");
  if (!tEl || !sEl) return null;
  const trigger = Number(tEl.value);
  const stop = Number(sEl.value);
  return { st: st, trigger: trigger, stop: stop, nums: _scenarioNumbers(st, trigger, stop) };
}

/* Compare two trigger/stop pairs; the server ask is skipped when they match. */
function _samePrices(a, b) {
  if (!a || !b) return false;
  if (!Number.isFinite(Number(a.trigger)) || !Number.isFinite(Number(b.trigger))) return false;
  return Math.abs(Number(a.trigger) - Number(b.trigger)) < 1e-9
      && Math.abs(Number(a.stop) - Number(b.stop)) < 1e-9;
}

/* Ask the server about a trigger/stop pair. Debounced 250 ms, only one request
   in flight, and answers are remembered per price pair, so a drag does not
   hammer the API. */
function _askSizing(pair) {
  const st = _researchState;
  if (!st) return;
  const p = pair || _readPrices();
  if (!p || !(Number(p.trigger) > 0) || !(Number(p.stop) > 0)) return;
  if (_samePrices(p, st.lastSizing)) return;
  st.pendingSizing = p;
  if (st.sizingTimer) clearTimeout(st.sizingTimer);
  st.sizingTimer = setTimeout(_flushSizing, 250);
}

function _flushSizing() {
  const st = _researchState;
  if (!st) return;
  if (st.sizingInFlight) return;               // the in-flight answer re-checks
  const want = st.pendingSizing;
  if (!want) return;
  st.pendingSizing = null;
  const cacheKey = want.trigger + "|" + want.stop;
  st.sizingCache = st.sizingCache || {};
  if (st.sizingCache[cacheKey]) {               // already answered
    st.lastSizing = want;
    return;
  }
  const shape = (st.data.current_setup || {}).shape_score;
  const shapeNum = shape !== null && shape !== undefined && shape !== ""
    && Number.isFinite(Number(shape)) ? Number(shape) : null;
  const url = "/api/sizing/" + encodeURIComponent(st.data.symbol || "")
    + "?trigger=" + encodeURIComponent(want.trigger)
    + "&stop=" + encodeURIComponent(want.stop)
    + (shapeNum === null ? "" : "&shape=" + encodeURIComponent(shapeNum));
  st.sizingInFlight = true;
  const call = (typeof window.api === "function") ? window.api : api;
  st.lastSizing = want;
  Promise.resolve()
    .then(() => call(url))
    .then((res) => {
      st.sizingInFlight = false;
      if (_researchState !== st) return;
      if (!res || res.error) { _sizingFallback(res); _flushSizing(); return; }
      st.sizingCache[cacheKey] = res;
      /* The server's own caps only land once we have asked it. */
      if (Number(res.capital) > 0) st.capital = Number(res.capital);
      _updateWhatIf();
      _flushSizing();
    })
    .catch(() => {
      st.sizingInFlight = false;
      if (_researchState !== st) return;
      _sizingFallback(null);
      _flushSizing();
    });
}

function _refreshPriceInputs() {
  const st = _researchState;
  if (!st) return;
  const tEl = document.getElementById("whatIfTrigger");
  const sEl = document.getElementById("whatIfStop");
  if (!tEl || !sEl) return;
  if (document.activeElement !== tEl) tEl.value = st.live.trigger == null ? "" : String(st.live.trigger);
  if (document.activeElement !== sEl) sEl.value = st.live.stop == null ? "" : String(st.live.stop);
}

/* Read both price boxes as the owner has them right now. */
function _readPrices() {
  const tEl = document.getElementById("whatIfTrigger");
  const sEl = document.getElementById("whatIfStop");
  if (!tEl || !sEl) return null;
  return { trigger: Number(tEl.value), stop: Number(sEl.value) };
}

function _sizingFallback(res) {
  const st = _researchState;
  if (!st) return;
  const warn = document.getElementById("wiWarn");
  const when = new Date().toLocaleTimeString();
  st.sizingDown = when;
  if (warn) {
    warn.hidden = false;
    warn.textContent = "The terminal could not check the account rules at "
      + when + ", so the figures below use the standard rule (a fixed slice of "
      + "your money, and a cap on how much goes into one idea). Everything you "
      + "drag still works.";
  }
  const pad = document.getElementById("wiPad");
  if (pad) {
    pad.hidden = false;
    pad.className = "slider-note";
    pad.textContent = "The numbers above come from the rules this screen already "
      + "knows, not from a fresh check with the server.";
  }
  if (res && res.error) {
    console.warn("sizing API returned an error:", res.error);
  }
}

/* Build the sliders once per panel. A drag only repaints read-outs, so nothing
   is rebuilt while a finger is on the control. */
function _bindWhatIfHost(box, data) {
  if (_slidersBound && _slidersBound === box) return;
  _slidersBound = box;
  const pane = document.getElementById("whatIfSliders");
  const st = _researchState;
  if (!pane || !st || typeof window.makeSlider !== "function") return;
  pane.innerHTML = "";
  try {
    const capNow = Number(st.capital) > 0 ? Number(st.capital) : 500000;
    const capitalMax = Math.max(
      2000000,
      Math.ceil((capNow * 4) / 100000) * 100000
    );
    const capitalStep = Math.max(10000, Math.round(capitalMax / 200 / 1000) * 1000);
    pane.appendChild(window.makeSlider({
      id: "whatIfCapital",
      label: "Money you could put into shares altogether",
      min: 50000,
      max: capitalMax,
      step: capitalStep,
      value: capNow,
      suffix: " rupees",
      hint: "Your whole pot, not just this one idea. A smaller pot buys fewer shares, and the most you could lose gets smaller with it.",
      explainKey: "sizing",
      onInput: () => _updateWhatIf()
    }));

    pane.appendChild(window.makeSlider({
      id: "whatIfRisk",
      label: "Most you are willing to lose on this idea",
      min: 0.25,
      max: 5,
      step: 0.25,
      value: Number(st.riskPct) > 0 ? Number(st.riskPct) : 1,
      suffix: "% of your money",
      hint: "A loss should be small enough that a run of them does not end the game. Slide it and watch the shares and the loss move together.",
      explainKey: "risk_pct",
      onInput: () => _updateWhatIf()
    }));
  } catch (e) {
    pane.innerHTML = `<p class="slider-note">The sliders could not start in this browser. The figures still work from the prices in the boxes above.</p>`;
    return;
  }

  /* Date window: how far back the setups table below looks. The window is
     counted backwards from the newest setup in the file, so the newest row is
     always inside it. */
  const rowsAll = (data.raw_setups || []).filter(
    r => r && /^\d{4}-\d{2}-\d{2}/.test(String(r.signal_date)));
  const newest = rowsAll.reduce(
    (m, r) => String(r.signal_date) > m ? String(r.signal_date) : m, "");
  const oldest = rowsAll.reduce(
    (m, r) => (!m || String(r.signal_date) < m) ? String(r.signal_date) : m, "");
  if (rowsAll.length && newest) {
    const span = Math.max(30, Math.ceil(
      (Date.parse(newest + "T00:00:00Z") - Date.parse(oldest + "T00:00:00Z")) / 86400000) + 15);
    const dateMax = Math.min(2000, Math.max(st.dateDays || 1000, span));
    st.dateMax = dateMax;
    const step = Math.max(5, Math.round(dateMax / 100 / 5) * 5);
    pane.appendChild(window.makeSlider({
      id: "whatIfWindow",
      label: "How far back to look at past setups",
      min: 5,
      max: dateMax,
      step: step,
      value: Math.min(dateMax, Math.max(5, st.dateDays || dateMax)),
      suffix: " days",
      hint: "The list of past setups below keeps only the ones inside this window. The hit rates and averages above still use the symbol's whole history.",
      onInput: (v) => {
        st.dateDays = v;
        _rebuildDateTable();
      }
    }));
  } else {
    const p = document.createElement("p");
    p.className = "slider-note";
    p.textContent = "This symbol's history came back without a date on each setup, so the date window cannot be offered. The table below shows every setup it has.";
    p.setAttribute("data-explain", "sizing");
    pane.appendChild(p);
  }

  const useClose = document.getElementById("whatIfUseClose");
  if (useClose) {
    useClose.addEventListener("click", () => {
      const closeNow = Number(data.latest_close);
      if (!Number.isFinite(closeNow) || closeNow <= 0) return;
      st.live.trigger = closeNow;
      st.live.stop = Number((closeNow * 0.99).toFixed(2));
      _refreshPriceInputs();
      _updateWhatIf();
      _askSizing({ trigger: st.live.trigger, stop: st.live.stop });
    });
  }

  ["whatIfTrigger", "whatIfStop"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    /* 'input' is instant and stays local; 'change' is when the phone keyboard is
       done, which is the right moment to ask the server. */
    el.addEventListener("input", () => _updateWhatIf());
    el.addEventListener("change", () => {
      _updateWhatIf();
      _askSizing();
    });
  });

  _refreshPriceInputs();
  _updateWhatIf();
  if (st.sizingDown) _sizingFallback(null);
}

/* ------------------------------------------------- date window on the table */

/* raw_setups carries one signal_date per row, so the window can also work by
   counting rows when the window is longer than the whole history. */
function _filterByWindow(rows, days) {
  if (!rows || !rows.length) return { rows: [], note: "" };
  const withDate = rows.filter(r => r && /^\d{4}-\d{2}-\d{2}/.test(String(r.signal_date)));
  if (!withDate.length) {
    /* No usable per-row date: do not fake a filter, say so. */
    return { rows: rows, note: "This data has no date on each row, so the window cannot filter it." };
  }
  const newest = withDate.reduce(
    (m, r) => String(r.signal_date) > String(m) ? String(r.signal_date) : m,
    String(withDate[0].signal_date));
  const cutoff = new Date(Date.parse(newest + "T00:00:00Z"));
  cutoff.setUTCDate(cutoff.getUTCDate() - Number(days));
  const cut = cutoff.toISOString().slice(0, 10);
  let kept = withDate.filter(r => String(r.signal_date) >= cut);
  let note = "";
  if (!kept.length) {
    const newestN = Math.max(1, Math.min(12, withDate.length));
    kept = withDate.slice(0, newestN);
    note = "Nothing in this symbol's history was found inside the last "
      + Number(days) + " days, so the " + newestN
      + " most recent setups are shown instead. The newest one is "
      + _shortDate(newest) + ".";
  } else if (kept.length >= 40) {
    kept = kept.slice(0, 40);
    note = "Showing the 40 most recent setups inside your window.";
  }
  return { rows: kept, note: note };
}

function _renderHistoryTable(host, data) {
  if (!host) return;
  const st = _researchState;
  if (!st || !data.history_sufficient || !data.raw_setups || !data.raw_setups.length) {
    host.innerHTML = "";
    return;
  }
  const filtered = _filterByWindow(data.raw_setups, st.dateDays);
  const rows = filtered.rows;
  st.dateTable = {
    rows: rows,
    note: filtered.note,
    total: data.raw_setups.length,
    from: rows.length ? _shortDate(rows[rows.length - 1].signal_date) : "",
    to: rows.length ? _shortDate(rows[0].signal_date) : ""
  };
  if (!rows.length) {
    host.innerHTML = `<p class="slider-note">No past setups are dated inside this window.</p>`;
    return;
  }
  let html = `<h4 style="margin:14px 0 8px; font-size:13px;">Past setups in the window you chose — showing ${rows.length} of ${data.raw_setups.length} (from ${_shortDate(rows[rows.length - 1].signal_date)} to ${_shortDate(rows[0].signal_date)})</h4>`;
  if (filtered.note) html += `<p class="slider-note">${_esc(filtered.note)}</p>`;
  html += `<table style="width:100%; border-collapse:collapse; font-size:12px;">
    <thead><tr style="text-align:left; color:#9fb0cc; border-bottom:1px solid rgba(255,255,255,.1);">
      <th style="padding:6px 4px;">Signal</th>
      <th style="padding:6px 4px;">Entry</th>
      <th style="padding:6px 4px;">Mother</th>
      <th style="padding:6px 4px;">Trig</th>
      <th style="padding:6px 4px;">MFE</th>
      <th style="padding:6px 4px;">MAE</th>
      <th style="padding:6px 4px;">Outcome</th>
    </tr></thead><tbody>`;
  rows.forEach((s, index) => {
    html += `<tr class="click-row" tabindex="0" role="button"
      data-window-index="${index}"
      style="border-bottom:1px solid rgba(255,255,255,.05);">
      <td style="padding:6px 4px;">${s.signal_date}</td>
      <td style="padding:6px 4px;">${s.entry}</td>
      <td style="padding:6px 4px;">${s.mother_type || "—"}</td>
      <td style="padding:6px 4px;">${s.triggered ? "✓" : "✗"}</td>
      <td style="padding:6px 4px;">${_num(s.mfe_r)}R</td>
      <td style="padding:6px 4px;">${_num(s.mae_r)}R</td>
      <td style="padding:6px 4px;">${s.outcome}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  host.innerHTML = html;
  /* These rows are already bound to the payload, but the table was rebuilt. */
  _bindWindowRows(host, rows);
}

function _bindWindowRows(host, rows) {
  host.querySelectorAll("[data-window-index]").forEach((row) => {
    const setup = rows[Number(row.dataset.windowIndex)];
    if (!setup) return;
    const open = () => window.openDataDetail?.(
      `${(_researchState && _researchState.data.symbol) || ""} · setup ${setup.signal_date}`,
      setup);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

function _rebuildDateTable(box) {
  const st = _researchState;
  if (!st) return;
  const host = document.getElementById("historyTableHost");
  if (!host) return;
  /* The slider owns the window; the read fallback keeps the last value if the
     control is not on screen yet. */
  const el = document.getElementById("sld-whatIfWindow");
  if (el && Number.isFinite(Number(el.value))) st.dateDays = Number(el.value);
  _renderHistoryTable(host, st.data);
  const note = document.getElementById("dateWindowEffect");
  const t = st.dateTable;
  if (!note) return;
  if (!t) {
    note.textContent = "";
    note.hidden = true;
    return;
  }
  note.hidden = false;
  let text = "The table below is filtered: " + t.rows.length + " of " + t.total
    + " past setups" + (t.from ? " (" + t.from + " to " + t.to + ")" : "") + ".";
  if (st.dateDays >= (st.dateMax || 1000)) {
    text = "The table below shows all " + t.total + " past setups, newest first.";
  }
  text += " The hit rates and averages above still cover the symbol's whole history — this window only picks out which setups you look at.";
  note.textContent = text;
}

/* ------------------------------------------------------------- research UI */

function renderResearch(data) {
  const box = document.getElementById("researchBox");
  if (!box) return;
  if (data.error) {
    box.textContent = `Research unavailable: ${data.error}`;
    return;
  }
  const h = data.historical || {};
  const state = data.market_state || {};
  const st = _getResearchState(data);
  _researchState = st;
  st.data = data;
  /* The panel's HTML is replaced below, so the sliders have to be rebuilt. */
  _slidersBound = null;
  let html = "";

  html += `<div style="font-size:12px; color:#7f8da9; margin-bottom:6px;">
    ${data.sector || "Unknown sector"} · as of ${data.as_of} ·
    close ${data.latest_close} · ${data.pct_from_52w_high}% below 52w high ·
    ${data.pct_from_52w_low}% above 52w low
  </div>`;
  const emaStatus = ["ema20", "ema50", "ema200"]
    .filter(key => state[key] != null)
    .map(key => `${Number(state.close) >= Number(state[key]) ? "above" : "below"} ${key.slice(3).toUpperCase()}`)
    .join(" · ") || "EMA context unavailable";
  const marketPct = value => value == null || !Number.isFinite(Number(value))
    ? "—" : `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(1)}%`;
  html += `<div class="setup-box">
    <h4 style="margin:0 0 8px;font-size:13px;">Latest market state · ${state.as_of || data.as_of || "date unavailable"}</h4>
    <div class="fx-row"><span>Close / daily change</span><strong>${_num(state.close)} · ${marketPct(state.change_1d_pct)}</strong></div>
    <div class="fx-row"><span>20 / 60 session move</span><strong>${marketPct(state.change_20d_pct)} · ${marketPct(state.change_60d_pct)}</strong></div>
    <div class="fx-row"><span>Trend context</span><strong>${emaStatus}</strong></div>
    <div class="fx-row"><span>Volume vs 20-session average</span><strong>${state.volume_ratio_20 == null ? "unavailable" : `${_num(state.volume_ratio_20)}×`}</strong></div>
    <p class="method-note">This is observed end-of-day price behaviour, not a forecast. ${state.bars_available || data.history_bars_tested || 0} daily bars available in the analysis window.</p>
  </div>`;

  if (data.current_setup) {
    const cs = data.current_setup;
    html += `<div class="fx-row" style="padding:8px 12px; border-left:3px solid #34d399;">
      <span><b style="color:#34d399;">LIVE SETUP TODAY</b> — signal ${cs.signal_date}</span>
      <strong>entry ${cs.entry} · stop ${cs.stop} · 3R ${cs.target_3r}</strong>
    </div>`;
    html += _researchRow("Risk %", cs.risk_pct + "%");
    html += _researchRow("Pullback", cs.pullback_pct + "% over " + cs.pullback_days + "d");
    html += _researchRow("Impulse", cs.impulse_pct + "%");
    html += _researchRow("EMA zone", cs.ema_zone);
    html += _researchRow("Shape score", cs.shape_score + "/100");
    if (cs.mother_type) {
      html += _researchRow("Mother bar", cs.mother_type);
    }
  } else {
    html += `<div class="fx-row" style="padding:8px 12px; border-left:3px solid #7f8da9;">
      <span>LIVE SETUP</span><strong>none triggered today</strong>
    </div>`;
  }

  // Signature match comes right after live setup — it's the global view.
  html += _renderSignatureBlock(data);

  // Symbol-only history
  html += `<h4 style="margin:14px 0 8px; font-size:13px;">Symbol history — ${h.n_setups || 0} setups over ${data.history_years}y (step ${data.step})</h4>`;

  if (!data.history_sufficient) {
    html += `<p>Historical setup statistics need at least 280 daily bars. Only ${data.history_bars_tested || 0} are available; the latest market state above is still shown.</p>`;
    html += _renderWhatIfPanel(data);
    html += `<div id="historyTableHost"></div>`;
    box.innerHTML = html;
    _bindResearchDetails(box, data);
    _bindWhatIf(box, data);
    return;
  }
  if (!h.n_setups) {
    html += `<p>No historical setups matched the configured rules in the available sample.</p>`;
    html += _renderWhatIfPanel(data);
    html += `<div id="historyTableHost"></div>`;
    box.innerHTML = html;
    _bindResearchDetails(box, data);
    _bindWhatIf(box, data);
    return;
  }
  html += _researchRow("Triggered",
    `${h.n_triggered} of ${h.n_setups} (P=${_pctStr(h.p_trigger)})`);
  html += `<div class="fx-row" style="padding:8px 12px;">
    <span>Hit rate<span class="ledger-sight" data-explain="hit_rate" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does hit rate mean?">?</span></span>
    <strong>+1R ${_pctStr(h.p_1r_given_trigger)} · +2R ${_pctStr(h.p_2r_given_trigger)} · +3R ${_pctStr(h.p_3r_given_trigger)}</strong>
  </div>`;
  html += `<div class="fx-row" style="padding:8px 12px;">
    <span>MFE in R<span class="ledger-sight" data-explain="mfe" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does MFE mean?">?</span></span>
    <strong>median ${_num(h.median_mfe_r)} · p95 ${_num(h.p95_mfe_r)}</strong>
  </div>`;
  html += `<div class="fx-row" style="padding:8px 12px;">
    <span>MAE in R<span class="ledger-sight" data-explain="mae" tabindex="0" role="button" title="Click to learn what this means" aria-label="What does MAE mean?">?</span></span>
    <strong>median ${_num(h.median_mae_r)} · p5 ${_num(h.p5_mae_r)}</strong>
  </div>`;

  // Candle block
  html += _renderCandleBlock(data);

  /* The slider box sits where it is used, before the historical table it can
     filter. */
  html += _renderWhatIfPanel(data);

  // The historical table is rendered by _rebuildDateTable so the date slider
  // can redraw just this part.
  html += `<div id="historyTableHost"></div>`;

  box.innerHTML = html;
  _bindResearchDetails(box, data);
  _bindWhatIf(box, data);
}

/* Wire the slider box after its HTML is in the document. sliders.js is injected
   here because index.html is owned elsewhere; if it never arrives the box still
   shows the figures from the two price boxes and says what happened. */
function _bindWhatIf(box, data) {
  _bindWhatIfHost(box, data);
  _rebuildDateTable(box);
  _loadSliders().then((ok) => {
    if (_researchState !== _getResearchState(data)) return;
    if (!ok) {
      _slidersBound = null;
      const pane = document.getElementById("whatIfSliders");
      if (pane) {
        pane.innerHTML = `<p class="slider-note">The sliders could not load on this page, so only the two price boxes above are adjustable. Everything else still works.</p>`;
      }
      _rebuildDateTable(box);
      return;
    }
    _bindWhatIfHost(box, data);
    _rebuildDateTable(box);
  }).catch(() => {
    _rebuildDateTable(box);
  });
}

function _bindResearchDetails(box, data) {
  const sm = data.signature_match;
  if (sm && sm.sample_matches) {
    box.querySelectorAll("[data-match-index]").forEach((row) => {
      const match = sm.sample_matches[Number(row.dataset.matchIndex)];
      if (!match) return;
      const open = () => window.jumpResearch?.(match.symbol);
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    });
  }
  box.querySelectorAll("[data-candle-key]").forEach((row) => {
    const candle = (data.candle_stats || {})[row.dataset.candleKey];
    const open = () => window.openDataDetail?.(
      `${data.symbol} · ${row.dataset.candleKey} candle history`, candle);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
  /* The old fixed "recent setups" rows are kept for any payload that still
     renders them; the slider table binds its own rows. */
  box.querySelectorAll("[data-history-index]").forEach((row) => {
    const setup = (data.recent_setups || [])[Number(row.dataset.historyIndex)];
    if (!setup) return;
    const open = () => window.openDataDetail?.(
      `${data.symbol} · setup ${setup.signal_date}`, setup);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

/* The research payload itself does not carry the sizing answer, so the panel
   asks for it once after it has rendered. If that call fails the panel keeps
   every figure it can compute and says so in words. */
function _primeSizing() {
  const st = _researchState;
  if (!st) return;
  const prices = _readPrices();
  if (!prices || !(prices.trigger > 0) || !(prices.stop > 0)) return;
  _askSizing(prices);
}

async function loadResearch(symbol) {
  const box = document.getElementById("researchBox");
  if (!box) return;
  const requestId = ++_researchRequestId;
  /* A different symbol starts from its own prices; the same symbol keeps
     whatever the owner already dragged. */
  const remembered = _researchState;
  box.innerHTML = `<p>Computing (5-15s)...</p>`;
  try {
    const data = await api(`/api/research/${symbol}`);
    if (requestId !== _researchRequestId) return;
    if (remembered && remembered.data
        && String(remembered.data.symbol || "").toUpperCase()
           !== String(data.symbol || symbol || "").toUpperCase()) {
      _researchState = null;
    }
    renderResearch(data);
    _primeSizing();
  } catch (e) {
    if (requestId === _researchRequestId) {
      box.textContent = `Research error: ${e.message}`;
    }
  }
}

window.loadResearch = loadResearch;
