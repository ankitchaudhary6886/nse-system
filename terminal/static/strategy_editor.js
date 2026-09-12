// In-browser strategy editor — no JSON, no files.
// Opens a modal when any strategy card's "Edit" button is pressed.

const STRATEGY_FIELDS = [
  // Price / bar structure
  "close", "open", "high", "low", "volume",
  "close_gt_open", "inside_day",
  "atr_14", "atr_pct",
  // Trend / MAs
  "dma20", "dma50", "dma200",
  "above20", "above50", "above200",
  "high52", "low52",
  "distance_from_52w_high", "distance_from_52w_low",
  // Momentum
  "mom_5d", "mom_20d", "mom_60d",
  "rsi",
  // Volume
  "vol_ratio_20", "avg_vol_20",
  // Sector
  "sector_rs",
  // Episodic Pivot features
  "had_gapup_15d", "days_since_gapup", "gapup_size",
  "pre_gap_above50", "pre_gap_above200", "pre_gap_drawdown",
  // RCP / impulse features
  "impulse_pct_60d", "days_since_impulse_peak",
  "pullback_from_peak_pct", "consolidation_range_pct",
  // Fundamentals
  "roce", "pe", "pb", "roe", "debt_to_equity",
  "profit_growth_3y", "sales_growth_3y",
  "promoter_holding", "dividend_yield",
  "cfo_positive", "market_cap_cr",
  "operating_margin", "net_profit_margin",
];

const STRATEGY_OPS = ["==", "!=", ">", ">=", "<", "<="];
const UNIVERSES = ["active", "band", "combined"];

// ---------- Modal scaffolding (created once, reused) ----------
function _ensureEditorModal() {
  let root = document.getElementById("strategyEditorRoot");
  if (root) return root;
  root = document.createElement("div");
  root.id = "strategyEditorRoot";
  root.style.cssText = `
    display: none;
    position: fixed; inset: 0;
    background: rgba(0,0,0,.65);
    z-index: 9999;
    overflow-y: auto;
    padding: 24px;
  `;
  root.innerHTML = `
    <div id="strategyEditorCard" style="
      max-width: 820px; margin: 0 auto;
      background: #0d1220;
      border: 1px solid rgba(255,255,255,.15);
      border-radius: 16px;
      padding: 22px;
      color: #edf3ff;
    ">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <h2 id="strategyEditorTitle" style="margin:0; font-size:20px;">Edit strategy</h2>
        <button id="strategyEditorClose" style="background:none; border:none; color:#9fb0cc; font-size:22px; cursor:pointer;">×</button>
      </div>
      <div id="strategyEditorBody"></div>
      <div style="display:flex; gap:10px; margin-top:18px;">
        <button id="strategyEditorSave" style="padding:10px 22px; border-radius:10px; background:rgba(52,211,153,.2); color:#34d399; border:1px solid rgba(52,211,153,.4); font-weight:700; cursor:pointer;">Save</button>
        <button id="strategyEditorCancel" style="padding:10px 22px; border-radius:10px; background:rgba(255,255,255,.05); color:#9fb0cc; border:1px solid rgba(255,255,255,.1); font-weight:700; cursor:pointer;">Cancel</button>
        <span id="strategyEditorStatus" style="align-self:center; color:#9fb0cc; font-size:13px;"></span>
      </div>
    </div>
  `;
  document.body.appendChild(root);
  root.addEventListener("click", (e) => {
    if (e.target === root) _closeEditor();
  });
  document.getElementById("strategyEditorClose").addEventListener("click", _closeEditor);
  document.getElementById("strategyEditorCancel").addEventListener("click", _closeEditor);
  return root;
}

function _closeEditor() {
  const root = document.getElementById("strategyEditorRoot");
  if (root) root.style.display = "none";
}

// ---------- Form rendering ----------
function _optionsHtml(list, selected) {
  return list.map(v =>
    `<option value="${v}" ${v === selected ? "selected" : ""}>${v}</option>`
  ).join("");
}

function _renderConditionRow(cond) {
  return `
    <tr class="cond-row" style="border-bottom:1px solid rgba(255,255,255,.06);">
      <td style="padding:6px 4px;">
        <select class="cond-field" style="min-width:180px;">
          ${_optionsHtml(STRATEGY_FIELDS, cond.field)}
        </select>
      </td>
      <td style="padding:6px 4px;">
        <select class="cond-op" style="min-width:60px;">
          ${_optionsHtml(STRATEGY_OPS, cond.op)}
        </select>
      </td>
      <td style="padding:6px 4px;">
        <input class="cond-value" type="number" step="any" value="${cond.value}" style="width:120px;"/>
      </td>
      <td style="padding:6px 4px; text-align:right;">
        <button class="cond-remove" title="Remove" style="background:none;border:none;color:#fb7185;font-size:16px;cursor:pointer;">✕</button>
      </td>
    </tr>`;
}

function _renderWeightRow(field, weight) {
  return `
    <tr class="weight-row" style="border-bottom:1px solid rgba(255,255,255,.06);">
      <td style="padding:6px 4px;">
        <select class="weight-field" style="min-width:180px;">
          ${_optionsHtml(STRATEGY_FIELDS, field)}
        </select>
      </td>
      <td style="padding:6px 4px;">
        <input class="weight-value" type="number" step="any" value="${weight}" style="width:120px;"/>
      </td>
      <td style="padding:6px 4px; text-align:right;">
        <button class="weight-remove" title="Remove" style="background:none;border:none;color:#fb7185;font-size:16px;cursor:pointer;">✕</button>
      </td>
    </tr>`;
}

function _populateEditor(name, s) {
  const body = document.getElementById("strategyEditorBody");
  document.getElementById("strategyEditorTitle").textContent = "Edit: " + name;

  const conditionsHtml = (s.conditions || []).map(_renderConditionRow).join("");
  const weightsHtml = Object.entries(s.score_weights || {})
    .map(([f, w]) => _renderWeightRow(f, w)).join("");

  body.innerHTML = `
    <div style="display:grid; gap:12px;">
      <label style="display:flex; gap:10px; align-items:center;">
        <span style="width:110px; color:#9fb0cc;">Name</span>
        <input id="edName" type="text" value="${name}" style="flex:1; padding:8px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:8px; color:#edf3ff;"/>
      </label>
      <label style="display:flex; gap:10px; align-items:center;">
        <span style="width:110px; color:#9fb0cc;">Description</span>
        <input id="edDesc" type="text" value="${(s.description || "").replace(/"/g, '&quot;')}" style="flex:1; padding:8px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:8px; color:#edf3ff;"/>
      </label>
      <label style="display:flex; gap:10px; align-items:center;">
        <span style="width:110px; color:#9fb0cc;">Type</span>
        <select id="edType" style="padding:8px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:8px; color:#edf3ff;">
          ${_optionsHtml(["fundamental", "swing"], s.type || "swing")}
        </select>
      </label>
      <label style="display:flex; gap:10px; align-items:center;">
        <span style="width:110px; color:#9fb0cc;">Universe</span>
        <select id="edUniv" style="padding:8px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:8px; color:#edf3ff;">
          ${_optionsHtml(UNIVERSES, s.universe || "band")}
        </select>
      </label>
    </div>

    <h3 style="margin:20px 0 8px; font-size:15px;">Conditions (all must pass)</h3>
    <table style="width:100%; border-collapse:collapse;">
      <thead>
        <tr style="text-align:left; color:#7f8da9; font-size:11px; text-transform:uppercase;">
          <th style="padding:6px 4px;">Field</th>
          <th style="padding:6px 4px;">Op</th>
          <th style="padding:6px 4px;">Value</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="condRows">${conditionsHtml}</tbody>
    </table>
    <button id="addConditionBtn" style="margin-top:8px; padding:6px 14px; border-radius:8px; background:rgba(96,165,250,.12); color:#60a5fa; border:1px solid rgba(96,165,250,.3); cursor:pointer;">+ Add condition</button>

    <h3 style="margin:20px 0 8px; font-size:15px;">Score weights (optional)</h3>
    <table style="width:100%; border-collapse:collapse;">
      <thead>
        <tr style="text-align:left; color:#7f8da9; font-size:11px; text-transform:uppercase;">
          <th style="padding:6px 4px;">Field</th>
          <th style="padding:6px 4px;">Weight</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="weightRows">${weightsHtml}</tbody>
    </table>
    <button id="addWeightBtn" style="margin-top:8px; padding:6px 14px; border-radius:8px; background:rgba(96,165,250,.12); color:#60a5fa; border:1px solid rgba(96,165,250,.3); cursor:pointer;">+ Add weight</button>
  `;

  // Event wiring
  document.getElementById("addConditionBtn").addEventListener("click", () => {
    const tb = document.getElementById("condRows");
    tb.insertAdjacentHTML("beforeend",
      _renderConditionRow({field: "close", op: ">=", value: 0}));
    _wireDynamicRows();
  });
  document.getElementById("addWeightBtn").addEventListener("click", () => {
    const tb = document.getElementById("weightRows");
    tb.insertAdjacentHTML("beforeend",
      _renderWeightRow("close", 1.0));
    _wireDynamicRows();
  });
  _wireDynamicRows();
}

function _wireDynamicRows() {
  document.querySelectorAll(".cond-remove").forEach(btn => {
    btn.onclick = () => btn.closest("tr").remove();
  });
  document.querySelectorAll(".weight-remove").forEach(btn => {
    btn.onclick = () => btn.closest("tr").remove();
  });
}

function _collectEditor() {
  const name = document.getElementById("edName").value.trim();
  const description = document.getElementById("edDesc").value.trim();
  const type = document.getElementById("edType").value;
  const universe = document.getElementById("edUniv").value;

  const conditions = [];
  document.querySelectorAll("#condRows .cond-row").forEach(tr => {
    const field = tr.querySelector(".cond-field").value;
    const op = tr.querySelector(".cond-op").value;
    const value = parseFloat(tr.querySelector(".cond-value").value);
    if (!Number.isNaN(value)) {
      conditions.push({field, op, value});
    }
  });

  const score_weights = {};
  document.querySelectorAll("#weightRows .weight-row").forEach(tr => {
    const field = tr.querySelector(".weight-field").value;
    const w = parseFloat(tr.querySelector(".weight-value").value);
    if (!Number.isNaN(w)) {
      score_weights[field] = w;
    }
  });

  return { name, description, type, universe, conditions, score_weights };
}

async function _saveEditor() {
  const status = document.getElementById("strategyEditorStatus");
  const payload = _collectEditor();
  if (!payload.name) {
    status.textContent = "Name is required";
    status.style.color = "#fb7185";
    return;
  }
  if (!payload.conditions.length) {
    status.textContent = "At least one condition required";
    status.style.color = "#fb7185";
    return;
  }
  status.textContent = "Saving...";
  status.style.color = "#9fb0cc";
  try {
    await api(`/api/strategies/${encodeURIComponent(payload.name)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    status.textContent = "Saved";
    status.style.color = "#34d399";
    // Refresh strategy lists
    if (typeof loadStrategyListFor === "function") {
      loadStrategyListFor("fundamental");
      loadStrategyListFor("swing");
    }
    setTimeout(_closeEditor, 400);
  } catch (e) {
    status.textContent = "Save failed: " + e.message;
    status.style.color = "#fb7185";
  }
}

// ---------- Public API ----------
window.openStrategyEditor = async function (name) {
  _ensureEditorModal();
  const root = document.getElementById("strategyEditorRoot");
  root.style.display = "block";
  const body = document.getElementById("strategyEditorBody");
  body.innerHTML = "<p>Loading...</p>";
  try {
    const s = await api(`/api/strategies/${encodeURIComponent(name)}`);
    if (!s || s.error) {
      body.innerHTML = `<p>Could not load strategy: ${s && s.error || "unknown"}</p>`;
      return;
    }
    _populateEditor(name, s);
    document.getElementById("strategyEditorSave").onclick = _saveEditor;
  } catch (e) {
    body.innerHTML = `<p>Error: ${e.message}</p>`;
  }
};